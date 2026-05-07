UPDATE "system"
SET "value" = 'true'
WHERE "key" = 'is_setup_complete';


INSERT INTO "users" ("username",
                     "password",
                     "salt",
                     "name",
                     "email",
                     "external",
                     "active",
                     "roles",
                     "changetimestamp")
SELECT 'admin',
       'SHA=__CF_REMOTE_SHA__',
       '__CF_REMOTE_SALT__',
       'admin',
       'admin@organisation.com',
       FALSE,
       '1',
       '{admin,cf_remoteagent}',
       now() ON CONFLICT (username,
                          EXTERNAL) DO
UPDATE
SET password = 'SHA=__CF_REMOTE_SHA__',
    salt = '__CF_REMOTE_SALT__';
