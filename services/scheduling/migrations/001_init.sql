CREATE TABLE date_polls (
    id INT IDENTITY(1,1) PRIMARY KEY,
    title NVARCHAR(200) NOT NULL,
    range_start DATE NOT NULL,
    range_end DATE NOT NULL,
    trip_length INT NOT NULL CONSTRAINT ck_date_polls_trip_length CHECK (trip_length >= 1),
    created_at DATETIME2 NOT NULL CONSTRAINT df_date_polls_created_at DEFAULT SYSUTCDATETIME()
);

CREATE TABLE availability (
    id INT IDENTITY(1,1) PRIMARY KEY,
    date_poll_id INT NOT NULL
        CONSTRAINT fk_availability_date_poll REFERENCES date_polls(id) ON DELETE CASCADE,
    participant NVARCHAR(100) NOT NULL,
    day DATE NOT NULL,
    CONSTRAINT uq_availability UNIQUE (date_poll_id, participant, day)
);
