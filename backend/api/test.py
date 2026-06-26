import sys, os, json

async def app(scope, receive, send):
    assert scope["type"] == "http"

    info = {
        "status": "ok",
        "version": sys.version,
        "path": sys.path,
        "cwd": os.getcwd(),
        "env_keys": sorted(k for k in os.environ if not "SECRET" in k.upper() and not "KEY" in k.upper()),
    }
    body = json.dumps(info).encode()

    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
