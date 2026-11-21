-- Expand-only: existing rows get 'normal', and the previous revision (which inserts without
-- this column) keeps working while CD rolls out the new one.
ALTER TABLE tasks ADD priority NVARCHAR(10) NOT NULL
    CONSTRAINT df_tasks_priority DEFAULT 'normal'
    CONSTRAINT ck_tasks_priority CHECK (priority IN ('low', 'normal', 'high'));
