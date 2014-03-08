CREATE TABLE ajxp_changes ( seq INTEGER PRIMARY KEY AUTOINCREMENT, node_id NUMERIC, type TEXT, source TEXT, target TEXT )
CREATE TABLE ajxp_index ( node_id INTEGER PRIMARY KEY AUTOINCREMENT, node_path TEXT, bytesize NUMERIC, md5 TEXT, mtime NUMERIC, stat_result BLOB)
CREATE TABLE ajxp_last_buffer ( id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, source TEXT, target TEXT )
CREATE TABLE "ajxp_node_status" ("node_id" INTEGER PRIMARY KEY  NOT NULL , "status" TEXT NOT NULL  DEFAULT 'IDLE', "detail" TEXT)
CREATE TRIGGER LOG_DELETE AFTER DELETE ON ajxp_index BEGIN INSERT INTO ajxp_changes (node_id,source,target,type) VALUES (old.node_id, old.node_path, "NULL", "delete"); END
CREATE TRIGGER LOG_INSERT AFTER INSERT ON ajxp_index BEGIN INSERT INTO ajxp_changes (node_id,source,target,type) VALUES (new.node_id, "NULL", new.node_path, "create"); END
CREATE TRIGGER "LOG_UPDATE_CONTENT" AFTER UPDATE ON "ajxp_index" FOR EACH ROW  WHEN old.node_path=new.node_path BEGIN INSERT INTO ajxp_changes (node_id,source,target,type) VALUES (new.node_id, old.node_path, new.node_path, "content"); END
CREATE TRIGGER "LOG_UPDATE_PATH" AFTER UPDATE ON "ajxp_index" FOR EACH ROW  WHEN old.node_path!=new.node_path BEGIN INSERT INTO ajxp_changes (node_id,source,target,type) VALUES (new.node_id, old.node_path, new.node_path, "path"); END
CREATE TRIGGER "STATUS_DELETE" AFTER DELETE ON "ajxp_index" BEGIN DELETE FROM ajxp_node_status WHERE node_id=old.node_id; END
CREATE TRIGGER "STATUS_INSERT" AFTER INSERT ON "ajxp_index" BEGIN INSERT INTO ajxp_node_status (node_id) VALUES (new.node_id); END