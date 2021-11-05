import psycopg2

class Properties:
    def __init__(self, db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str):
        self.db_addr = db_addr
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass
        self._connected = False
        self._conn = None

    @property
    def conn_string(self) -> str:
        return f'host={self.db_addr} port={self.db_port} dbname={self.db_name}' \
                f' user={self.db_user} password={self.db_pass}'
    @property
    def conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.conn_string)
            try:
                with self._conn.cursor() as cur:
                    cur.execute('SELECT 1')
                    assert cur.fetchone()[0] == 1
                self._connected = True
            except Exception:
                self._connected = False
                raise
        return self._conn
    
    def close(self):
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
        self._connected = False
    
    @property
    def connected(self):
        return self._connected