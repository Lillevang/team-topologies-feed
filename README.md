# Team Topologies Blog – Unofficial RSS Feed

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker Pulls](https://img.shields.io/docker/pulls/lillevang/teamtopologies-feed.svg)](https://hub.docker.com/r/lillevang/teamtopologies-feed)

This is an **unofficial** RSS feed generator for the [Team Topologies blog](https://teamtopologies.com/blog).  
The blog does not currently offer an RSS/Atom feed, so this service scrapes the latest posts and exposes them in a standard RSS 2.0 format.

## ✨ Features
- ✅ Fetches latest blog posts from [teamtopologies.com/blog](https://teamtopologies.com/blog)
- ✅ Outputs valid RSS 2.0 feed at `/feed.xml`
- ✅ Simple FastAPI service, easy to deploy anywhere
- ✅ Local caching to reduce network load
- ✅ Configurable cache TTL and feed size

## 🚀 Quick start

### Using Docker
```bash
docker run -d \
  --name teamtopologies-feed \
  -p 8080:8080 \
  -v teamtopologies-cache:/data \
  -e CACHE_TTL=900 \
  -e MAX_ITEMS=20 \
  lillevang/teamtopologies-feed:latest
```

Access your feed at:

```
http://localhost:8080/feed.xml
```

### Running locally (Python 3.11+)

```
git clone https://github.com/Lillevang/teamtopologies-feed.git
cd teamtopologies-feed
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

mkdir -p .cache
export CACHE_FILE="$(pwd)/.cache/cache.json"
uvicorn app:app --host 0.0.0.0 --port 8080
```

### Configuration

| Variable     | Default                   | Description                              |
| ------------ | ------------------------- | ---------------------------------------- |
| `CACHE_FILE` | `/data/cache.json`        | Path to cache file                       |
| `CACHE_TTL`  | `900`                     | Cache lifetime in seconds                |
| `MAX_ITEMS`  | `20`                      | Max number of items in generated feed    |
| `USER_AGENT` | `MinifluxFeedGen/1.0`     | Custom HTTP User-Agent for blog requests |

### Endpoints

- `/feed.xml` -> RSS 2.0 feed
- `/` -> Basic health check ({"ok": true})


### Notes

- This is **unoficcial** and not affiliated with the authors of Team Topologies
- The service is designed for personal/home use (e.g. Synology NAS, Minflux, FreshRSS)


### License

This project is licensed under the MIT License -- see the [LICENSE](LICENSE) file for details

