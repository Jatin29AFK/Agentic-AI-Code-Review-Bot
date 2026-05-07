const localApiBaseUrl = `${window.location.protocol}//${window.location.hostname}:8000`;
const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
const API_BASE_URL = configuredApiBaseUrl || (import.meta.env.DEV ? localApiBaseUrl : "");

async function request(path, options = {}) {
  if (!API_BASE_URL) {
    throw new Error("VITE_API_BASE_URL is not configured for this deployment.");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let message = "Request failed";
    try {
      const data = await response.json();
      message = data.detail || data.message || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export const api = {
  getHealth: () => request("/health"),
  getReviews: () => request("/api/reviews"),
  getReview: (reviewId) => request(`/api/reviews/${reviewId}`),
  getReviewDetails: (reviewId) => request(`/api/reviews/${reviewId}/details`),
  getCommentPreview: (reviewId) => request(`/api/reviews/${reviewId}/comment-preview`),
  getAutofixDrafts: (reviewId) => request(`/api/reviews/${reviewId}/autofix`),
  regenerateAutofixDrafts: (reviewId) =>
    request(`/api/reviews/${reviewId}/autofix/regenerate`, {
      method: "POST",
    }),
  createManualReview: (payload) =>
    request("/api/reviews/manual", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  postComments: (reviewId, payload) =>
    request(`/api/reviews/${reviewId}/post-comments`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
