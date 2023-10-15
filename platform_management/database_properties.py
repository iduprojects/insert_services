# pylint: disable=too-many-instance-attributes,too-many-arguments
"""
Database connection wrapper class `Properties` is defined here.
"""
import psycopg2
from loguru import logger


class Properties:
    """
    Database connection wrapper.
    """

    def __init__(self, db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str, connect_timeout: int = 10):
        self.db_addr = db_addr
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass
        self.connect_timeout = connect_timeout
        self._conn = None
        self._connected = False

    def reopen(self, db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str):
        """
        Close old connection if possible and update database credentials.
        """
        self.close()
        self.db_addr = db_addr
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass
        self._conn = None

    def copy(self) -> "Properties":
        """
        Return a new database connection with the same credentials.
        """
        return Properties(
            self.db_addr,
            self.db_port,
            self.db_name,
            self.db_user,
            self.db_pass,
            connect_timeout=self.connect_timeout,
        )

    @property
    def conn_string(self) -> str:
        """
        Connection string used for a database connection.
        """
        return (
            f"host={self.db_addr} port={self.db_port} dbname={self.db_name}"
            f" user={self.db_user} password={self.db_pass}"
            f" application_name=insert_services"
            f" connect_timeout={self.connect_timeout}"
        )

    @property
    def conn(self) -> psycopg2.extensions.connection:
        """
        Database connection object if the connection was successfull. Raises exception otherwise.
        """
        if self._conn is None or self._conn.closed:
            try:
                self._conn = psycopg2.connect(self.conn_string)
            except psycopg2.OperationalError:
                self._conn = None
                raise
        try:
            with self._conn.cursor() as cur:  # type: ignore
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1  # type: ignore
        except Exception:
            self._conn = None
            raise
        return self._conn

    def close(self):
        """
        Close database connection.
        """
        if self._conn is not None and not self._conn.closed:
            try:
                self._conn.close()
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("couldn't close database connection: {!r}", exc)
        self._conn = None

    @property
    def connected(self) -> bool:
        """
        True if the connection was established
        """
        return self.conn is not None
