A set of command to handle CKB members and forum users.

# Usage

- Locally restore CKB members and forum mysql dumps, as "ckb" and
  "kayakbreforum" respectively (default behaviour with mysqldump --database).
  Set `$MYSQL_PASSWORD` to the local db root password.
- Setup the project environment:

        $ git clone https://github.com/pmezard/ckb-users.git
        $ cd ckbusers
        $ python3 -m virtualenv .
        $ source bin/activate
        $ pip install -r requirements.txt

- Export users in csv files:

        $ ./users.py list ckb.csv forum.csv

- Cross-check both datasets:

        $ ./users.py match ckb.csv forum.csv --unknown-path unknown.csv

Fill unknown.csv `delete` column and cleanup the forum.

For the deletion part :

- Define `CKB_FORUM_USER` and `CKB_FORUM_PASSWORD`
- List identifiers of users to delete, one per line, in a file.
- Delete the users:

        $ cat user_ids.txt | xargs ./users.py delete_users
