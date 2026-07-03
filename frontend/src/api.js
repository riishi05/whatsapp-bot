import axios from "axios";

const api = axios.create({ baseURL: "/api" });

export const getTenants = () => api.get("/dashboard/tenants").then((r) => r.data);
export const getSessions = (tenantId) =>
  api.get(`/dashboard/tenants/${tenantId}/sessions`).then((r) => r.data);
export const getThread = (tenantId, phoneNumber) =>
  api.get(`/dashboard/tenants/${tenantId}/sessions/${phoneNumber}/messages`).then((r) => r.data);
export const sendBroadcast = (payload) => api.post("/broadcast", payload).then((r) => r.data);

export default api;
