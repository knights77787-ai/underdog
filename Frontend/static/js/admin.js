// 관리자 페이지 - API 호출 시 쿠키 포함 (credentials: 'include')
const API_BASE = window.APP_CONFIG?.API_BASE || "";

async function adminFetch(path, options = {}) {
  const url = (API_BASE || "") + path;
  const res = await fetch(url, {
    ...options,
    credentials: "include",
    headers: { ...(options.headers || {}) },
  });
  if (res.status === 401) {
    window.location.href = "/admin-login";
    throw new Error("Unauthorized");
  }
  return res;
}
