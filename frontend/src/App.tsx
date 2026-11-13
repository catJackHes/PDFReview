import { useEffect, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

type Project = {
  id: string;
  name: string;
  description?: string | null;
  status: string;
  created_by: string;
  created_at: string;
};

type ReviewRun = {
  id: string;
  project_id: string;
  status: string;
  engine_version: string;
  created_by: string;
  started_at: string;
  completed_at?: string | null;
};

export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('pdfreview_token'));
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState('样例招投标项目');
  const [reviewRuns, setReviewRuns] = useState<ReviewRun[]>([]);

  const api = (path: string, options: RequestInit = {}) => {
    return fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    }).then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || 'Request failed');
      }
      return data;
    });
  };

  const login = async () => {
    const result = await api('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    setToken(result.access_token);
    localStorage.setItem('pdfreview_token', result.access_token);
  };

  const logout = () => {
    setToken(null);
    localStorage.removeItem('pdfreview_token');
  };

  const loadProjects = async () => {
    const data = await api('/projects');
    setProjects(data);
    if (data.length && !currentProjectId) {
      setCurrentProjectId(data[0].id);
    }
  };

  const createProject = async () => {
    const data = await api('/projects', {
      method: 'POST',
      body: JSON.stringify({ name: projectName, description: '从前端创建的样例项目' }),
    });
    setProjectName('');
    await loadProjects();
    setCurrentProjectId(data.id);
  };

  const triggerReview = async () => {
    if (!currentProjectId) return;
    const list = await api(`/projects/${currentProjectId}/reviews`, {
      method: 'POST',
      body: JSON.stringify({
        file_ids: [],
        rule_set: 'default',
        options: { enable_ocr: true },
      }),
    });
    setReviewRuns((prev) => [list, ...prev]);
  };

  useEffect(() => {
    if (token) {
      loadProjects().catch((error) => console.error(error));
    }
  }, [token]);

  useEffect(() => {
    if (!currentProjectId || !token) return;
    api(`/projects/${currentProjectId}/reviews`)
      .then(setReviewRuns)
      .catch((error) => console.error(error));
  }, [currentProjectId, token]);

  if (!token) {
    return (
      <div className="page-shell">
        <div className="card auth-card">
          <h1>PDF 招投标审查系统</h1>
          <p>登录进入项目与审查流程</p>
          <label>
            用户名
            <input value={username} onChange={(e) => setUsername(e.target.value)} />
          </label>
          <label>
            密码
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          <button onClick={login}>登录</button>
        </div>
      </div>
    );
  }

  return (
    <div className="page-shell">
      <div className="card dashboard">
        <header>
          <div>
            <h1>项目管理</h1>
            <small>已登录：{username}</small>
          </div>
          <button className="secondary" onClick={logout}>退出</button>
        </header>

        <section className="operator-row">
          <input value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="项目名称" />
          <button onClick={createProject}>新建项目</button>
          <button className="secondary" onClick={triggerReview}>触发审查</button>
        </section>

        <div className="grid">
          <div className="panel">
            <h2>项目列表</h2>
            {projects.length === 0 ? <p>暂无项目</p> : (
              <ul className="list-box">
                {projects.map((project) => (
                  <li
                    key={project.id}
                    className={currentProjectId === project.id ? 'selected' : ''}
                    onClick={() => setCurrentProjectId(project.id)}
                  >
                    <strong>{project.name}</strong>
                    <span>{project.status}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="panel">
            <h2>审查运行</h2>
            {reviewRuns.length === 0 ? <p>尚未创建审查运行</p> : (
              <ul className="list-box">
                {reviewRuns.map((run) => (
                  <li key={run.id}>
                    <strong>{run.status}</strong>
                    <span>{run.engine_version}</span>
                    <small>{new Date(run.started_at).toLocaleString()}</small>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
