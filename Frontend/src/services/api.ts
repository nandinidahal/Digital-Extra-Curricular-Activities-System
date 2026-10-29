import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL ?? "/api";

export const tokenStorage = {
  get access() { return localStorage.getItem("xca_access"); },
  get refresh() { return localStorage.getItem("xca_refresh"); },
  set(access: string, refresh?: string) {
    localStorage.setItem("xca_access", access);
    if (refresh) localStorage.setItem("xca_refresh", refresh);
  },
  clear() {
    localStorage.removeItem("xca_access");
    localStorage.removeItem("xca_refresh");
  },
};

const api = axios.create({ baseURL: API_URL });

// Attach the access token to every request
api.interceptors.request.use((config) => {
  const token = tokenStorage.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// When the access token expires (401), refresh it once and retry the request
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry && tokenStorage.refresh) {
      original._retry = true;
      try {
        const { data } = await axios.post(`${API_URL}/auth/refresh/`, { refresh: tokenStorage.refresh });
        tokenStorage.set(data.access);
        original.headers.Authorization = `Bearer ${data.access}`;
        return api(original);
      } catch {
        tokenStorage.clear();
        window.location.href = `${import.meta.env.BASE_URL}login`;
      }
    }
    return Promise.reject(error);
  }
);

export default api;
