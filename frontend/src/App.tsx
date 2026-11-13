import { useCallback, useEffect, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

type Project = { id: string; name: string; description?: string | null; status: string };
type ProjectFile = {
  id: string; project_id: string; display_name: string; file_type: string;
  size_bytes: number; page_count: number; pdf_type: string; status: string; sha256: string;
};
type ReviewRun = {
  id: string; project_id: string; status: string; phase?: string; progress?: number;
  engine_version: string; started_at: string; completed_at?: string | null;
};
type Evidence = {
  id: string; page_number: number; text_excerpt?: string | null;
  bbox: number[]; source: string; confidence: number;
};
type Finding = {
  id: string; review_run_id: string; project_id: string; file_id?: string | null;
  category: string; message: string; severity: string; machine_result: string;
  review_status: string; confidence: number; source: string; created_at: string;
};
type HistoryItem = {
  id: string; action: string; previous_status: string; new_status: string;
  remark?: string | null; created_at: string;
};

export default function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('pdfreview_token'));
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState('');
  const [projectName, setProjectName] = useState('');
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [runs, setRuns] = useState<ReviewRun[]>([]);
  const [runId, setRunId] = useState('');
  const [findings, setFindings] = useState<Finding[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [remark, setRemark] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const api = useCallback(async (path: string, init: RequestInit = {}) => {
    const headers = new Headers(init.headers);
    if (token) headers.set('Authorization', `Bearer ${token}`);
    if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    const response = await fetch(`${API_URL}${path}`, { ...init, headers });
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.detail || data?.error?.message || `请求失败 (${response.status})`);
    return data;
  }, [token]);

  const loadProjects = useCallback(async () => {
    const result = await api('/projects');
    setProjects(result);
    if (!projectId && result.length) setProjectId(result[0].id);
  }, [api, projectId]);

  const loadProjectData = useCallback(async (id: string) => {
    const [fileRows, runRows] = await Promise.all([
      api(`/projects/${id}/files`), api(`/projects/${id}/reviews`),
    ]);
    setFiles(fileRows);
    setRuns(runRows);
    const nextRunId = runId && runRows.some((run: ReviewRun) => run.id === runId) ? runId : runRows[0]?.id || '';
    setRunId(nextRunId);
    if (nextRunId) {
      setFindings(await api(`/projects/${id}/reviews/${nextRunId}/findings`));
    } else {
      setFindings([]);
      setSelectedFinding(null);
      setEvidence([]);
      setHistory([]);
    }
  }, [api, runId]);

  useEffect(() => {
    if (!token) return;
    loadProjects().catch((e) => setError(e.message));
  }, [token, loadProjects]);

  useEffect(() => {
    if (!token || !projectId) return;
    loadProjectData(projectId).catch((e) => setError(e.message));
  }, [token, projectId]);

  const login = async (event: React.FormEvent) => {
    event.preventDefault(); setError(''); setBusy(true);
    try {
      const result = await api('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
      localStorage.setItem('pdfreview_token', result.access_token);
      setToken(result.access_token);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const logout = () => {
    localStorage.removeItem('pdfreview_token'); setToken(null); setProjects([]); setProjectId('');
  };

  const createProject = async () => {
    if (!projectName.trim()) return setError('请输入项目名称');
    setError(''); setBusy(true);
    try {
      const project = await api('/projects', { method: 'POST', body: JSON.stringify({ name: projectName.trim() }) });
      setProjectName(''); await loadProjects(); setProjectId(project.id); setNotice('项目已创建');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const uploadFiles = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files || []);
    if (!projectId || !selected.length) return;
    setError(''); setBusy(true);
    try {
      for (const file of selected) {
        const body = new FormData(); body.append('file', file); body.append('file_type', 'contract');
        await api(`/projects/${projectId}/files`, { method: 'POST', body });
      }
      await loadProjectData(projectId); setNotice(`已上传 ${selected.length} 个文件`);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); event.target.value = ''; }
  };

  const createReview = async () => {
    if (!projectId) return;
    if (!files.length) return setError('请先上传 PDF 文件');
    setError(''); setBusy(true);
    try {
      const run = await api(`/projects/${projectId}/reviews`, {
        method: 'POST', body: JSON.stringify({ file_ids: files.map((file) => file.id), rule_set: 'default', options: {} }),
      });
      setRunId(run.id); await loadProjectData(projectId); setNotice('审查运行已完成');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const selectRun = async (id: string) => {
    setRunId(id); setSelectedFinding(null); setEvidence([]); setHistory([]);
    try { setFindings(await api(`/projects/${projectId}/reviews/${id}/findings`)); }
    catch (e) { setError((e as Error).message); }
  };

  const selectFinding = async (finding: Finding) => {
    setSelectedFinding(finding); setRemark(''); setError('');
    try {
      const [evidenceRows, historyRows] = await Promise.all([
        api(`/findings/${finding.id}/evidence`), api(`/findings/${finding.id}/history`),
      ]);
      setEvidence(evidenceRows); setHistory(historyRows);
    } catch (e) { setError((e as Error).message); }
  };

  const reviewFinding = async (action: 'confirmed_issue' | 'confirmed_ok' | 'unable_to_judge') => {
    if (!selectedFinding) return;
    setBusy(true); setError('');
    try {
      await api(`/findings/${selectedFinding.id}/actions`, { method: 'POST', body: JSON.stringify({ action, remark: remark || null }) });
      const refreshed = await api(`/projects/${projectId}/reviews/${runId}/findings`);
      setFindings(refreshed);
      const current = refreshed.find((item: Finding) => item.id === selectedFinding.id);
      if (current) await selectFinding(current);
      setNotice('复核意见已保存并记录审计历史');
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const downloadReport = async (format: 'json' | 'html') => {
    if (!runId) return;
    setBusy(true); setError('');
    try {
      const response = await fetch(`${API_URL}/reports/${runId}?format=${format}`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error('报告生成失败');
      const blob = await response.blob(); const url = URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url; link.download = `review-${runId}.${format}`;
      link.click(); URL.revokeObjectURL(url);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  if (!token) return (
    <main className="login-page">
      <form className="login-card" onSubmit={login}>
        <div className="brand-mark">PDF</div><p className="eyebrow">BID DOCUMENT REVIEW</p>
        <h1>招投标审查工作台</h1><p className="muted">登录以管理项目、审查文件并复核结果</p>
        <label>用户名<input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} /></label>
        <label>密码<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p className="alert error">{error}</p>}
        <button disabled={busy} className="primary full">{busy ? '登录中…' : '登录系统'}</button>
      </form>
    </main>
  );

  const currentProject = projects.find((project) => project.id === projectId);
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark small-mark">PDF</div><div><strong>审查工作台</strong><small>本地合同审查</small></div></div>
        <div className="side-label">项目空间</div>
        <div className="project-list">
          {projects.map((project) => <button key={project.id} className={`project-link ${project.id === projectId ? 'active' : ''}`} onClick={() => setProjectId(project.id)}>
            <span className="project-dot" />{project.name}
          </button>)}
          {!projects.length && <p className="side-empty">还没有项目</p>}
        </div>
        <div className="sidebar-bottom"><span className="user-avatar">{username.slice(0, 1).toUpperCase()}</span><div className="user-info"><strong>{username}</strong><small>本地用户</small></div><button className="icon-button" title="退出登录" onClick={logout}>↗</button></div>
      </aside>

      <section className="workspace">
        <header className="topbar"><div><p className="eyebrow">PROJECT / REVIEW</p><h1>{currentProject?.name || '项目管理'}</h1></div><div className="top-actions"><span className="secure-badge">● 本地数据</span><button className="secondary" onClick={() => downloadReport('html')} disabled={!runId || busy}>导出报告</button></div></header>
        {(error || notice) && <div className={`alert ${error ? 'error' : 'success'}`}>{error || notice}<button onClick={() => { setError(''); setNotice(''); }}>×</button></div>}

        <section className="toolbar panel-card">
          <div className="create-project"><input value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="新项目名称" onKeyDown={(e) => e.key === 'Enter' && createProject()} /><button className="primary" disabled={busy} onClick={createProject}>＋ 新建项目</button></div>
          <div className="toolbar-divider" />
          <label className={`upload-button ${!projectId || busy ? 'disabled' : ''}`}><input type="file" accept="application/pdf,.pdf" multiple disabled={!projectId || busy} onChange={uploadFiles} /><span>↑</span>{busy ? '处理中…' : '上传 PDF'}</label>
          <button className="primary review-button" disabled={!projectId || !files.length || busy} onClick={createReview}>开始审查 <span>→</span></button>
        </section>

        <div className="summary-row">
          <div className="metric panel-card"><span className="metric-icon blue">▤</span><div><small>项目文件</small><strong>{files.length}</strong></div></div>
          <div className="metric panel-card"><span className="metric-icon amber">◎</span><div><small>审查运行</small><strong>{runs.length}</strong></div></div>
          <div className="metric panel-card"><span className="metric-icon rose">!</span><div><small>待复核问题</small><strong>{findings.filter((item) => item.review_status === 'pending').length}</strong></div></div>
        </div>

        <div className="main-grid">
          <section className="panel-card documents-panel"><div className="section-heading"><div><p className="eyebrow">DOCUMENTS</p><h2>项目文件</h2></div><span className="count-pill">{files.length} 个文件</span></div>
            {!files.length ? <div className="empty-state"><span>▤</span><strong>还没有上传文件</strong><p>上传 PDF 后即可开始审查</p></div> : <div className="file-list">{files.map((file) => <div className="file-row" key={file.id}><span className="pdf-icon">PDF</span><div className="file-meta"><strong title={file.display_name}>{file.display_name}</strong><small>{file.pdf_type} · {file.page_count} 页 · {(file.size_bytes / 1024 / 1024).toFixed(2)} MB</small></div><span className="status-chip">{file.status}</span></div>)}</div>}
          </section>
          <section className="panel-card runs-panel"><div className="section-heading"><div><p className="eyebrow">RUN HISTORY</p><h2>审查记录</h2></div></div>
            {!runs.length ? <div className="empty-state compact-empty"><span>◷</span><p>尚无审查记录</p></div> : <div className="run-list">{runs.map((run) => <button key={run.id} className={`run-row ${runId === run.id ? 'chosen' : ''}`} onClick={() => selectRun(run.id)}><span className="run-indicator">✓</span><span className="run-meta"><strong>{new Date(run.started_at).toLocaleString()}</strong><small>{run.engine_version} · {run.phase || run.status}</small></span><span className="run-status">{run.status}</span></button>)}</div>}
          </section>
        </div>

        <section className="panel-card findings-panel"><div className="section-heading"><div><p className="eyebrow">FINDINGS & REVIEW</p><h2>审查结论 <span className="heading-count">{findings.length}</span></h2></div><div className="report-actions"><button className="text-button" onClick={() => downloadReport('json')} disabled={!runId || busy}>下载 JSON</button><button className="text-button" onClick={() => downloadReport('html')} disabled={!runId || busy}>下载 HTML</button></div></div>
          {!findings.length ? <div className="empty-state compact-empty"><span>✓</span><p>选择项目并运行审查，结果将在这里显示</p></div> : <div className="findings-layout"><div className="finding-list">{findings.map((finding) => <button key={finding.id} className={`finding-row ${selectedFinding?.id === finding.id ? 'chosen' : ''}`} onClick={() => selectFinding(finding)}><span className={`severity-dot ${finding.severity}`} /><span className="finding-copy"><strong>{finding.message}</strong><small>{finding.category} · 机器结果：{finding.machine_result}</small></span><span className={`review-chip ${finding.review_status}`}>{finding.review_status}</span></button>)}</div>
            <div className="review-detail">{!selectedFinding ? <div className="detail-placeholder">选择一条结论查看证据并提交复核意见</div> : <>
              <div className="detail-title"><div><span className="eyebrow">人工复核</span><h3>{selectedFinding.message}</h3></div><span className={`review-chip ${selectedFinding.review_status}`}>{selectedFinding.review_status}</span></div>
              <div className="detail-facts"><span>类别：{selectedFinding.category}</span><span>机器置信度：{Math.round(selectedFinding.confidence * 100)}%</span><span>来源：{selectedFinding.source}</span></div>
              <h4>证据定位</h4>{evidence.length ? evidence.map((item) => <div className="evidence-card" key={item.id}><strong>第 {item.page_number} 页 <small>置信度 {Math.round(item.confidence * 100)}%</small></strong><p>{item.text_excerpt || '无文本片段，需查看原 PDF 核验。'}</p><code>bbox: [{item.bbox.join(', ')}]</code></div>) : <p className="muted">没有保存证据定位，请人工核验原文件。</p>}
              <label className="remark-label">复核备注<textarea value={remark} onChange={(e) => setRemark(e.target.value)} placeholder="记录判断依据或后续处理建议…" /></label>
              <div className="review-controls"><button disabled={busy} className="review-issue" onClick={() => reviewFinding('confirmed_issue')}>确认问题</button><button disabled={busy} className="review-ok" onClick={() => reviewFinding('confirmed_ok')}>确认无问题</button><button disabled={busy} className="review-unsure" onClick={() => reviewFinding('unable_to_judge')}>无法判断</button></div>
              <h4>操作历史</h4>{history.length ? <ol className="history-list">{history.map((item) => <li key={item.id}><strong>{item.new_status}</strong><span>{item.remark || '无备注'}</span><small>{new Date(item.created_at).toLocaleString()}</small></li>)}</ol> : <p className="muted">暂无人工复核记录</p>}
            </>}</div></div>}
        </section>
        <footer>自动检测仅供辅助审查；低置信度或无证据结果需由业务人员核验，不构成法律意见。</footer>
      </section>
    </main>
  );
}
