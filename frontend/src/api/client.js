export class ApiError extends Error {
  constructor({ code, message, status, details }) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

async function parseJsonResponse(response) {
  const text = await response.text();

  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    throw new ApiError({
      code: "invalid_json",
      message: "The server returned an invalid response.",
      status: response.status,
    });
  }
}

function buildUrl(path, params = {}) {
  const url = new URL(`/api${path}`, window.location.origin);

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });

  return `${url.pathname}${url.search}`;
}

export async function request(path, options = {}) {
  const { params, headers, ...fetchOptions } = options;
  const response = await fetch(buildUrl(path, params), {
    credentials: "include",
    ...fetchOptions,
    headers: {
      Accept: "application/json",
      ...headers,
    },
  });
  const data = await parseJsonResponse(response);

  if (!response.ok) {
    const backendError = data?.error;

    throw new ApiError({
      code: backendError?.code ?? "request_failed",
      message: backendError?.message ?? `Request failed with status ${response.status}.`,
      status: response.status,
      details: backendError?.details,
    });
  }

  return data;
}

export function getHealth() {
  return request("/health");
}

export function getMatches(params) {
  return request("/matches", { params });
}

export function getMatch(matchId) {
  return request(`/matches/${matchId}`);
}

export function getFeaturedGames() {
  return request("/featured-games");
}

export function getBot(botId) {
  return request(`/bots/${botId}`);
}

export function updateBot(botId, bot) {
  return request(`/bots/${botId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(bot),
  });
}

export function createMatch(match) {
  return request("/matches", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(match),
  });
}

export function getMatchJob(jobId) {
  return request(`/match-jobs/${jobId}`);
}

export function getLiveMatchJob(jobId) {
  return request(`/match-jobs/${jobId}/live`);
}

export function getMatchJobs(params) {
  return request("/match-jobs", { params });
}

export function createBot(bot) {
  return request("/bots", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(bot),
  });
}

export function submitBotCode(botId, submission) {
  return request(`/bots/${botId}/submission`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(submission),
  });
}

export function getLeaderboard(params) {
  return request("/leaderboard", { params });
}

export function getBots(params) {
  return request("/bots", { params });
}

export function getCurrentUser() {
  return request("/auth/me");
}

export function getUserProfile(username) {
  return request(`/users/${encodeURIComponent(username)}`);
}

export function updateCurrentUser(user) {
  return request("/auth/me", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(user),
  });
}

export function loginUser(credentials) {
  return request("/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(credentials),
  });
}

export function registerUser(credentials) {
  return request("/auth/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(credentials),
  });
}

export function logoutUser() {
  return request("/auth/logout", {
    method: "POST",
  });
}
