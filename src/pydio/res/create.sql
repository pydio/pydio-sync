CREATE TABLE ajxp_changes ( seq INTEGER PRIMARY KEY AUTOINCREMENT, node_id NUMERIC, type TEXT, source TEXT, target TEXT, deleted_md5 TEXT )
CREATE TABLE ajxp_index ( node_id INTEGER PRIMARY KEY AUTOINCREMENT, node_path TEXT, bytesize NUMERIC, md5 TEXT, mtime NUMERIC, stat_result BLOB)
CREATE TABLE ajxp_last_buffer ( id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, location TEXT, source TEXT, target TEXT )
CREATE TABLE "ajxp_node_status" ("node_id" INTEGER PRIMARY KEY  NOT NULL , "status" TEXT NOT NULL  DEFAULT 'NEW', "detail" TEXT)
CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, type text, message text, source text, target text, action text, status text, date text)

CREATE TRIGGER LOG_DELETE AFTER DELETE ON ajxp_index BEGIN INSERT INTO ajxp_changes (node_id,source,target,type,deleted_md5) VALUES (old.node_id, old.node_path, "NULL", "delete", old.md5); END
CREATE TRIGGER LOG_INSERT AFTER INSERT ON ajxp_index BEGIN INSERT INTO ajxp_changes (node_id,source,target,type) VALUES (new.node_id, "NULL", new.node_path, "create"); END
CREATE TRIGGER "LOG_UPDATE_CONTENT" AFTER UPDATE ON "ajxp_index" FOR EACH ROW BEGIN INSERT INTO "ajxp_changes" (node_id,source,target,type) VALUES (new.node_id, old.node_path, new.node_path, CASE WHEN old.node_path = new.node_path THEN "content" ELSE "path" END);END
CREATE TRIGGER "STATUS_DELETE" AFTER DELETE ON "ajxp_index" BEGIN DELETE FROM ajxp_node_status WHERE node_id=old.node_id; END
CREATE TRIGGER "STATUS_INSERT" AFTER INSERT ON "ajxp_index" BEGIN INSERT INTO ajxp_node_status (node_id) VALUES (new.node_id); END

CREATE INDEX changes_node_id ON ajxp_changes( node_id )
CREATE INDEX changes_type ON ajxp_changes( type )
CREATE INDEX changes_node_source ON ajxp_changes( source )
CREATE INDEX index_node_id ON ajxp_index( node_id )
CREATE INDEX index_node_path ON ajxp_index( node_path )
CREATE INDEX index_bytesize ON ajxp_index( bytesize )
CREATE INDEX index_md5 ON ajxp_index( md5 )
CREATE INDEX node_status_status ON ajxp_node_status( status )