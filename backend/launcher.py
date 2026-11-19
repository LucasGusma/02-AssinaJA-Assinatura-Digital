"""Start FastAPI. Previous demonstration is archived in legacy/."""
import argparse
import os

import uvicorn


def main():
    parser = argparse.ArgumentParser(description='AssinaJA · FastAPI + React')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8765')))
    args = parser.parse_args()
    uvicorn.run('backend.app.main:app', host=args.host, port=args.port, proxy_headers=False, access_log=False)


if __name__ == '__main__':
    main()
