import http.server
import socketserver
import os

PORT = 3000
DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'hotel-frontend', 'build')

class SPAServerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        # Translate requested path into filesystem path
        fs_path = self.translate_path(self.path)
        # If the file does not exist and it is not a static asset, route to index.html
        if not os.path.exists(fs_path):
            ext = os.path.splitext(self.path)[1].lower()
            if ext not in ('.js', '.css', '.png', '.jpg', '.jpeg', '.ico', '.json', '.svg', '.map', '.woff', '.woff2', '.ttf'):
                self.path = '/index.html'
        return super().do_GET()

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), SPAServerHandler) as httpd:
        print(f"Serving SPA build at http://localhost:{PORT}")
        httpd.serve_forever()

