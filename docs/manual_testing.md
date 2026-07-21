# Manual Testing Guide — Swagger UI

Open `http://localhost:8000/docs` in your browser.

---

## Auth Flow

1. **POST /auth/register** — fill `email`, `full_name`, `password` → copy tokens
2. **POST /auth/login** — fill `username` (email), `password` → copy tokens
3. Click **Authorize** (top right), paste `access_token` → you're now authenticated for all user endpoints

---

## Standard User Flow (authenticated)

4. **POST /profile** — view your user details
5. **PATCH /profile** — update name/email
6. **POST /profile/password** — change password
7. **POST /sessions** → create a session → copy `id`
8. **GET /sessions** — list sessions
9. **PATCH /sessions/{session_id}** — rename
10. **POST /uploads/sessions/{session_id}** — upload a PDF/JPEG/PNG/WebP → copy `id`
11. **GET /uploads/sessions/{session_id}** — list session files
12. **POST /uploads/{upload_id}/download** — get presigned download URL
13. **DELETE /uploads/{upload_id}** — delete upload
14. **POST /sessions/{session_id}/messages** — send a chat message → SSE stream in response body
15. **GET /sessions/{session_id}/messages** — view chat history
16. **POST /stt** — upload audio file for transcription
17. **POST /auth/logout** — revoke current refresh token
18. **DELETE /sessions/{session_id}** — soft-delete session

---

## Admin Flow

Set `x-api-key` header in Swagger UI for these endpoints (click Authorize → enter your admin API key).

19. **GET /admin/stats** — dashboard metrics
20. **GET /admin/users** — list all users
21. **POST /admin/users/{user_id}/activate** — enable user
22. **POST /admin/users/{user_id}/deactivate** — disable user
23. **POST /knowledge** — upload a knowledge document (background processing)
24. **GET /knowledge** — list entries
25. **PATCH /knowledge/{entry_id}** — update metadata → triggers reprocessing
26. **POST /knowledge/search/test** — test hybrid search
27. **POST /knowledge/{entry_id}/download** — presigned download URL
28. **POST /knowledge/{entry_id}/reindex** — reprocess from scratch
29. **DELETE /knowledge/{entry_id}** — soft-delete
