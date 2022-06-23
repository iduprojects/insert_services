from typing import Optional

import psycopg2


class Properties:
    def __init__(self, db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str):
        self.db_addr = db_addr
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass
        self._conn = None

    def reopen(self, db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str):
        if self._conn is not None:
            self.close()
        self.db_addr = db_addr
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass
        self._conn = None
    def copy(self):
        return Properties(self.db_addr, self.db_port, self.db_name, self.db_user, self.db_pass)
    @property
    def conn_string(self) -> str:
        return f'host={self.db_addr} port={self.db_port} dbname={self.db_name}' \
                f' user={self.db_user} password={self.db_pass} application_name=insert_services'
    @property
    def conn(self) -> 'psycopg2.connection':
        if self._conn is None or self._conn.closed:
            try:
                self._conn = psycopg2.connect(self.conn_string, connect_timeout=10)
            except psycopg2.OperationalError:
                self._connected = False
                raise
        try:
            with self._conn.cursor() as cur: # type: ignore
                cur.execute('SELECT 1')
                assert cur.fetchone()[0] == 1 # type: ignore
        except Exception:
            self._connected = False
            raise
        return self._conn
    def close(self):
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
        self._conn = None
        
    @property
    def connected(self):
        return self.conn is not None
