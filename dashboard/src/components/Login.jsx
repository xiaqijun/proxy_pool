import { useState } from "react";

export default function Login({ onLogin, error }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (!username || !password || submitting) {
      return;
    }
    setSubmitting(true);
    try {
      await onLogin(username, password);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <span className="brand-dot" />
          <span>ProxyPool</span>
        </div>
        <h1>监控工作台</h1>
        <p className="login-subtitle">
          登录后可查看代理池、网关、WAF 指标和在线策略配置。
        </p>

        <form onSubmit={submit}>
          <label className="field">
            <span>用户名</span>
            <input
              autoFocus
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="MONITOR_AUTH_USER"
            />
          </label>
          <label className="field">
            <span>密码</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="MONITOR_AUTH_PASSWORD"
            />
          </label>

          {error ? <div className="form-error">{error}</div> : null}

          <button className="btn primary login-button" type="submit" disabled={submitting}>
            {submitting ? "登录中..." : "登录"}
          </button>
        </form>

        <p className="login-hint">
          账号由 <code>MONITOR_AUTH_USER</code> / <code>MONITOR_AUTH_PASSWORD</code> 配置。
        </p>
      </div>
    </div>
  );
}
