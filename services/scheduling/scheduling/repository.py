import db


def as_iso(value):
    return value.isoformat() if value is not None else None


def insert_poll(title, range_start, range_end, trip_length):
    with db.transaction() as cursor:
        cursor.execute(
            "INSERT INTO date_polls (title, range_start, range_end, trip_length) "
            "OUTPUT INSERTED.id VALUES (%s, %s, %s, %s)",
            (title, range_start, range_end, trip_length),
        )
        return cursor.fetchone()["id"]


def get_poll(poll_id):
    with db.transaction() as cursor:
        cursor.execute(
            "SELECT id, title, range_start, range_end, trip_length "
            "FROM date_polls WHERE id = %s",
            (poll_id,),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return {**row, "range_start": as_iso(row["range_start"]), "range_end": as_iso(row["range_end"])}


def get_availability(poll_id):
    with db.transaction() as cursor:
        cursor.execute(
            "SELECT participant, day FROM availability "
            "WHERE date_poll_id = %s ORDER BY participant, day",
            (poll_id,),
        )
        rows = cursor.fetchall()
    return [{"participant": row["participant"], "day": as_iso(row["day"])} for row in rows]


def replace_availability(poll_id, participant, days):
    with db.transaction() as cursor:
        cursor.execute(
            "DELETE FROM availability WHERE date_poll_id = %s AND participant = %s",
            (poll_id, participant),
        )
        if days:
            cursor.executemany(
                "INSERT INTO availability (date_poll_id, participant, day) VALUES (%s, %s, %s)",
                [(poll_id, participant, day) for day in days],
            )
