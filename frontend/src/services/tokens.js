// Access token lives in memory only; the refresh token is an httpOnly cookie
// the browser sends to /api/v1/auth/* (scripts can't read it). After a page
// load the auth store gets a fresh access token from /auth/refresh.
let accessToken = null

export const getAccessToken = () => accessToken
export const setAccessToken = (token) => { accessToken = token || null }
export const clearAccessToken = () => { accessToken = null }

// Sessions from before 2.2.111 kept both tokens in localStorage. Hand back the
// old refresh token once (so it can be exchanged for a cookie) and wipe both.
export const takeLegacyRefreshToken = () => {
  let legacy = null
  try {
    legacy = localStorage.getItem('refresh_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('access_token')
  } catch (e) { /* storage blocked */ }
  return legacy
}
