import db


def as_iso(value):
    return value.isoformat() if value is not None else None


def insert_trip_with_members(name, destination, member_names):
    with db.transaction() as cursor:
        cursor.execute(
            "INSERT INTO trips (name, destination) OUTPUT INSERTED.id VALUES (%s, %s)",
            (name, destination),
        )
        trip_id = cursor.fetchone()["id"]
        if member_names:
            cursor.executemany(
                "INSERT INTO members (trip_id, name) VALUES (%s, %s)",
                [(trip_id, member_name) for member_name in member_names],
            )
    return trip_id


def get_trip(trip_id):
    with db.transaction() as cursor:
        cursor.execute(
            "SELECT id, name, destination, start_date, end_date, date_poll_id "
            "FROM trips WHERE id = %s",
            (trip_id,),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return {**row, "start_date": as_iso(row["start_date"]), "end_date": as_iso(row["end_date"])}


def insert_member(trip_id, name):
    with db.transaction() as cursor:
        cursor.execute("INSERT INTO members (trip_id, name) VALUES (%s, %s)", (trip_id, name))


def get_members(trip_id):
    with db.transaction() as cursor:
        cursor.execute(
            "SELECT id, name FROM members WHERE trip_id = %s ORDER BY id",
            (trip_id,),
        )
        return cursor.fetchall()


def insert_task(trip_id, title, priority):
    with db.transaction() as cursor:
        cursor.execute(
            "INSERT INTO tasks (trip_id, title, priority) VALUES (%s, %s, %s)",
            (trip_id, title, priority),
        )


def get_tasks(trip_id):
    with db.transaction() as cursor:
        cursor.execute(
            "SELECT tasks.id, tasks.title, tasks.done, tasks.priority, members.name AS claimed_by "
            "FROM tasks LEFT JOIN members ON members.id = tasks.claimed_by "
            "WHERE tasks.trip_id = %s ORDER BY tasks.id",
            (trip_id,),
        )
        return cursor.fetchall()


def set_task_claim(task_id, member_id):
    with db.transaction() as cursor:
        cursor.execute("UPDATE tasks SET claimed_by = %s WHERE id = %s", (member_id, task_id))


def set_task_done(task_id):
    with db.transaction() as cursor:
        cursor.execute("UPDATE tasks SET done = 1 WHERE id = %s", (task_id,))


def set_trip_dates(trip_id, start_date, end_date, date_poll_id):
    with db.transaction() as cursor:
        cursor.execute(
            "UPDATE trips SET start_date = %s, end_date = %s, date_poll_id = %s WHERE id = %s",
            (start_date, end_date, date_poll_id, trip_id),
        )
