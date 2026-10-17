DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS workspaces;
DROP TYPE IF EXISTS document_status_enum;

CREATE TABLE workspaces (
    workspace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TYPE document_status_enum AS ENUM ('pending', 'processing', 'ready', 'failed');

CREATE TABLE documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_name TEXT NOT NULL,
    document_status document_status_enum NOT NULL DEFAULT 'pending',
    workspace_id UUID NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,  /* If a workspace is deleted then there is no business need to keep their documents */
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);