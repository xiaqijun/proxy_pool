async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "include",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { src: text };
    }
  }

  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent("monitor:unauthorized"));
    throw new Error(data?.src || "unauthorized");
  }
  if (!response.ok) {
    throw new Error(data?.src || data?.message || response.statusText);
  }
  return data;
}

export const api = {
  session: () => request("/dashboard/api/session"),
  login: (username, password) =>
    request("/dashboard/api/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request("/dashboard/api/logout", { method: "POST" }),
  overview: () => request("/dashboard/api/overview"),
  trends: (hours = 24) => request(`/dashboard/api/trends?hours=${hours}`),
  proxies: (params) => {
    const query = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        query.set(key, value);
      }
    });
    return request(`/dashboard/api/proxies?${query.toString()}`);
  },
  deleteProxy: (proxy) =>
    request("/dashboard/api/proxies/delete", {
      method: "POST",
      body: JSON.stringify({ proxy }),
    }),
  waf: (hours = 24) => request(`/dashboard/api/waf?hours=${hours}`),
  config: () => request("/dashboard/api/config"),
  setStrategy: (strategy) =>
    request("/dashboard/api/strategy", {
      method: "POST",
      body: JSON.stringify({ strategy }),
    }),
  health: () => request("/dashboard/api/health"),
};
