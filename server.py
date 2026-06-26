import cgi
import json
import mimetypes
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

ROOT = os.path.dirname(__file__)
MUSIC_DIR = ROOT
UPLOAD_DIR = os.path.join(ROOT, 'uploads')
DATA_FILE = os.path.join(ROOT, 'data', 'tracks.json')

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)


def sanitize_filename(name: str) -> str:
    name = os.path.basename(name or 'track')
    safe = ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in name)
    return safe or 'track'


def detect_genre(name: str) -> str:
    lower = name.lower()
    if any(token in lower for token in ['eminem', 'skriptonit', 'icegergert', 'vektor', 'xcho', 's9', 'ramos', 'rap']):
        return 'rap'
    if any(token in lower for token in ['maria', 'vanilla', 'love', 'baby', 'tini', 'pop']):
        return 'pop'
    return 'other'


def load_tracks() -> list:
    if not os.path.exists(DATA_FILE):
        initial_tracks = []
        if os.path.isdir(MUSIC_DIR):
            for filename in sorted(os.listdir(MUSIC_DIR)):
                if filename.lower().endswith(('.mp3', '.mp4', '.m4a', '.wav', '.ogg', '.aac')):
                    initial_tracks.append({
                        'id': str(uuid.uuid4()),
                        'title': os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ').strip(),
                        'sourcePath': f'/{filename}',
                        'genre': detect_genre(filename),
                        'likes': 0,
                        'comments': []
                    })
        with open(DATA_FILE, 'w', encoding='utf-8') as handle:
            json.dump(initial_tracks, handle, ensure_ascii=False, indent=2)
    with open(DATA_FILE, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def save_tracks(tracks: list) -> None:
    with open(DATA_FILE, 'w', encoding='utf-8') as handle:
        json.dump(tracks, handle, ensure_ascii=False, indent=2)


class MusicHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/tracks':
            self._send_json(load_tracks())
            return
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/tracks':
            self._handle_upload()
            return
        if parsed.path.startswith('/api/tracks/') and parsed.path.endswith('/like'):
            self._handle_like(parsed.path)
            return
        if parsed.path.startswith('/api/tracks/') and parsed.path.endswith('/comment'):
            self._handle_comment(parsed.path)
            return
        return super().do_POST()

    def _find_track(self, track_id: str):
        tracks = load_tracks()
        for track in tracks:
            if track.get('id') == track_id:
                return track, tracks
        return None, None

    def _handle_upload(self):
        ctype, pdict = cgi.parse_header(self.headers.get('Content-Type', ''))
        if not ctype.startswith('multipart/form-data'):
            self._send_json({'error': 'expected multipart/form-data'}, 400)
            return

        fields = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers.get('Content-Type', '')})
        title = (fields.getvalue('title') or '').strip()
        uploaded = fields['file'] if 'file' in fields else None

        if not title or not uploaded or not getattr(uploaded, 'filename', ''):
            self._send_json({'error': 'title and file are required'}, 400)
            return

        source_name = sanitize_filename(uploaded.filename)
        unique_name = f"{uuid.uuid4().hex}_{source_name}"
        upload_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(upload_path, 'wb') as handle:
            handle.write(uploaded.file.read())

        tracks = load_tracks()
        track = {
            'id': str(uuid.uuid4()),
            'title': title,
            'sourcePath': f'/uploads/{unique_name}',
            'genre': 'other',
            'likes': 0,
            'comments': []
        }
        tracks.append(track)
        save_tracks(tracks)
        self._send_json(track, 201)

    def _handle_like(self, path: str):
        track_id = path.rstrip('/').split('/')[-2]
        length = int(self.headers.get('Content-Length', '0'))
        payload = json.loads(self.rfile.read(length).decode('utf-8')) if length else {}
        track, tracks = self._find_track(track_id)
        if not track:
            self._send_json({'error': 'track not found'}, 404)
            return
        liked = payload.get('liked', False)
        if liked:
            track['likes'] = int(track.get('likes', 0)) + 1
        else:
            track['likes'] = max(0, int(track.get('likes', 0)) - 1)
        save_tracks(tracks)
        self._send_json(track)

    def _handle_comment(self, path: str):
        track_id = path.rstrip('/').split('/')[-2]
        length = int(self.headers.get('Content-Length', '0'))
        payload = json.loads(self.rfile.read(length).decode('utf-8')) if length else {}
        track, tracks = self._find_track(track_id)
        if not track:
            self._send_json({'error': 'track not found'}, 404)
            return
        text = (payload.get('text') or '').strip()
        if text:
            track.setdefault('comments', []).append({'id': str(uuid.uuid4()), 'text': text})
            save_tracks(tracks)
        self._send_json(track)

    def log_message(self, format, *args):
        return


if __name__ == '__main__':
    server = ThreadingHTTPServer(('0.0.0.0', 8000), MusicHandler)
    print('Server running on http://127.0.0.1:8000')
    server.serve_forever()
