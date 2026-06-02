# Pas-Oublie
DAD project


# Pas Oublié
> Not forgotten. Save and search your data at Pas Oublié and never forget them.

**Deployed:** http://157.230.115.70  
**API Docs:** http://157.230.115.70/docs  
**GitHub:** https://github.com/blackdavlet/Pas-Oublie

---

## Stack

- **Nginx 1.27** — API gateway, load balancer, WebSocket proxy
- **FastAPI** — RESTful API (2 replicas)
- **PostgreSQL + pgvector** — relational metadata + vector embeddings
- **SeaweedFS** — distributed object storage (MinIO turned out to not be open-source)
- **Redis** — pub/sub event bus, upload sessions, JWT cache
- **OpenAI text-embedding-3-small** — AI semantic search
- **gRPC** — internal service communication
- **Prometheus + Grafana** — observability
- **JWT** — stateless authentication

---

## Run

```bash
git clone https://github.com/blackdavlet/Pas-Oublie.git
cd Pas-Oublie
cp .env.example .env
# fill in .env 
docker compose up --build -d
docker compose exec pa_backend alembic upgrade head
```

---

## Environment Variables

```env
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_NAME=pasoublie
JWT_SECRET=your-secret-key
OPENAI_API_KEY=sk-proj-...
GF_SECURITY_ADMIN_PASWORD=admin123
```

---

## Structure

```
Pas-Oublie/
├── backend/
│   ├── app/
│   │   ├── main.py               # API endpoints
│   │   ├── db.py                 # Database (asyncpg)
│   │   ├── auth.py               # JWT
│   │   ├── ws.py                 # WebSocket
│   │   ├── seaweedfs_client.py   # File storage
│   │   ├── grpc_client.py        # gRPC client
│   │   └── snowflake.py          # ID generator (R11)
│   └── migrations/               # Alembic (R3)
├── storage_service/              # gRPC — download/delete
├── search_service/               # gRPC — semantic search
├── index-worker/                 # Redis consumer, AI indexing
├── frontend/                     # HTML/CSS/JS
├── postgres/init.sql
├── nginx/nginx.conf
├── prometheus/prometheus.yml
└── docker-compose.yml
```

---

## API

Full interactive docs at `/docs`. Key endpoints:

| Method | URL | Auth |
|--------|-----|------|
| POST | `/auth/register` | No |
| POST | `/auth/login` | No |
| POST | `/files/upload/init` | Yes |
| PUT | `/files/upload/{id}/chunk/{n}` | Yes |
| POST | `/files/upload/{id}/complete` | Yes |
| GET | `/files/{id}/download` | Yes |
| DELETE | `/files/{id}/delete` | Yes |
| GET | `/search?query=` | Yes |
| POST | `/workspaces` | Yes |
| POST | `/workspaces/{id}/members` | Yes |
| GET | `/workspaces/{id}/folders` | Yes |
| POST | `/folders` | Yes |

---

## Migrations

```bash
# apply
docker compose exec pa_backend alembic upgrade head

# rollback
docker compose exec pa_backend alembic downgrade -1
```

---

## Observability

- Prometheus: `http://YOUR_IP:9090`
- Grafana: `http://YOUR_IP:3000`

---

## Known Limitations

- Large file downloads stream through Python — slow for files > 500MB. We had to use presigned URLs(
- No TLS — HTTP only
- Search indexes .txt, .pdf, .docx only

---

## Team

| Name | ID | Role |
|------|----|------|
| Radjabov Davlat | U2310216 | Team Leader |
| Ismailov Damir | U2310104 | API Integrator |
| Komiljonova Mushtariybegim | U2310142 | Database Design |
| O'ktamjonova Farangis | U2210172 | Debugger |
| Pak Igor | U2310199 | DevOps |
| Biynazova Malika | U2310058 | Network Engineer |

---

*SOC3060 Database Application & Design — Spring 2026 — Inha University in Tashkent*
