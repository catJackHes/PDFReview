body {
  margin: 0;
  font-family: 'Segoe UI', sans-serif;
  background: #f4f6fb;
  color: #111827;
}

* {
  box-sizing: border-box;
}

button,
input {
  font: inherit;
}

button {
  border: none;
  border-radius: 8px;
  padding: 10px 16px;
  background: #2563eb;
  color: white;
  cursor: pointer;
}

button.secondary {
  background: #e5e7eb;
  color: #111827;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.page-shell {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
  padding: 24px;
  width: min(100%, 980px);
}

.auth-card {
  max-width: 420px;
}

.auth-card h1,
.dashboard h1 {
  margin: 0 0 8px;
}

.auth-card p {
  color: #4b5563;
  margin-bottom: 20px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
  font-weight: 600;
}

input {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px 12px;
}

.operator-row {
  display: flex;
  gap: 12px;
  align-items: center;
  margin: 20px 0;
}

.operator-row input {
  flex: 1;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.lower-grid {
  margin-top: 20px;
}

.panel {
  background: #f9fafb;
  border-radius: 12px;
  padding: 16px;
}

.panel h2 {
  margin-top: 0;
}

.list-box {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.list-box.compact li {
  font-size: 0.9rem;
}

.list-box li {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  background: white;
  cursor: pointer;
}

.list-box li.selected {
  border-color: #3b82f6;
  background: #eff6ff;
}

header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

small {
  color: #64748b;
}

.active-project {
  margin-bottom: 12px;
  padding: 12px 16px;
  background: #eff6ff;
  border-radius: 10px;
  color: #1d4ed8;
}

.upload-box {
  border: 1px dashed #93c5fd;
  border-radius: 10px;
  background: #f8fbff;
  padding: 10px;
}

@media (max-width: 768px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .operator-row {
    flex-direction: column;
    align-items: stretch;
  }
}
