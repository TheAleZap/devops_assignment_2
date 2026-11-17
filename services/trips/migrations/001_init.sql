CREATE TABLE trips (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(200) NOT NULL,
    destination NVARCHAR(200) NULL,
    start_date DATE NULL,
    end_date DATE NULL,
    date_poll_id INT NULL,  -- poll in the Scheduling service: a plain ID, no foreign key (ADR-3, ADR-7)
    created_at DATETIME2 NOT NULL CONSTRAINT df_trips_created_at DEFAULT SYSUTCDATETIME()
);

CREATE TABLE members (
    id INT IDENTITY(1,1) PRIMARY KEY,
    trip_id INT NOT NULL CONSTRAINT fk_members_trip REFERENCES trips(id) ON DELETE CASCADE,
    name NVARCHAR(100) NOT NULL,
    CONSTRAINT uq_members_trip_name UNIQUE (trip_id, name)
);

CREATE TABLE tasks (
    id INT IDENTITY(1,1) PRIMARY KEY,
    trip_id INT NOT NULL CONSTRAINT fk_tasks_trip REFERENCES trips(id) ON DELETE CASCADE,
    title NVARCHAR(200) NOT NULL,
    -- NO ACTION, not SET NULL: SQL Server rejects two cascade paths from trips to tasks (ADR-7)
    claimed_by INT NULL CONSTRAINT fk_tasks_member REFERENCES members(id),
    done BIT NOT NULL CONSTRAINT df_tasks_done DEFAULT 0
);
