#!/usr/bin/env python3
import csv
import datetime
import os
import re
import unicodedata

import click
import mysql.connector


@click.group()
def cli():
    pass


def _connect_mysql(dbname):
    socket = "/opt/local/var/run/mysql55/mysqld.sock"
    password = os.environ.get("MYSQL_PASSWORD")
    cnx = mysql.connector.connect(
        unix_socket=socket, user="root", database=dbname, password=password
    )
    return cnx


def list_ckb_users(season):
    cnx = _connect_mysql("ckb")
    cursor = cnx.cursor()
    q = """
    select p.id, p.nom, p.prenom, p.mail
        from personne p
        inner join adhesion a on (a.idPers = p.id)
        inner join saison s on (s.id = a.idSaison)
        where s.libelle = %s
        order by p.nom, p.prenom
    """
    cursor.execute(q, (season,))
    users = []
    for id, first_name, last_name, email in cursor:
        users.append((id, first_name, last_name, email))
    return users


def list_forum_users():
    cnx = _connect_mysql("kayakbreforum")
    cursor = cnx.cursor()
    q = "select id, username, realname, email, last_visit from users"
    cursor.execute(q)
    users = []
    for id, username, realname, email, last_visit in cursor:
        last_visit = datetime.datetime.fromtimestamp(last_visit)
        last_visit = last_visit.strftime("%Y-%m-%d")
        users.append((id, username, realname, email, last_visit))
    return users


def _write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(header)
        for row in rows:
            assert len(row) == len(header)
            w.writerow(row)


@cli.command("list")
@click.argument("ckb_path")
@click.argument("forum_path")
def list_(ckb_path, forum_path):
    """Export members and forum users from MySQL to csv"""
    season = "2018-2019"
    ckb_users = list_ckb_users(season)
    forum_users = list_forum_users()
    if ckb_path:
        _write_csv(ckb_path, ("id", "first_name", "last_name", "email"), ckb_users)
    if forum_path:
        _write_csv(
            forum_path,
            ("id", "username", "realname", "email", "last_visit"),
            forum_users,
        )


def _read_csv(path):
    rows = []
    with open(path, "r", encoding="utf-8") as fp:
        r = csv.reader(fp)
        for i, row in enumerate(r):
            if i == 0:
                continue
            rows.append(row)
    return rows


def remove_diacritics(text):
    try:
        # Fast path ascii string.
        text.encode("ascii")
        return text
    except UnicodeEncodeError:
        nkfd_form = unicodedata.normalize("NFKD", text)
        normalized = "".join([c for c in nkfd_form if not unicodedata.combining(c)])
        return normalized


def normalize(text):
    text = remove_diacritics(text)
    text = text.strip()
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text


class Matcher:
    def __init__(self, ckb_users):
        self.emails = {}
        self.full_names = {}
        for id, fname, lname, email in ckb_users:
            email = email.lower().strip()
            self.emails[email] = id
            # Handle '$first $last' and '$last $first' combinations
            fname = normalize(fname)
            lname = normalize(lname)
            self.full_names[fname + " " + lname] = id
            self.full_names[lname + " " + fname] = id

    def match(self, id, uname, email):
        matches = []

        if int(id) == 1:
            matches.append(("guest_user", id))

        email = email.lower().strip()
        if email in self.emails:
            matches.append(("email", self.emails[email]))

        uname = normalize(uname)
        if uname in self.full_names:
            matches.append(("full_name", self.full_names[uname]))

        return sorted(matches)


def _tabulate(rows):
    if not rows:
        return rows
    lengths = [0] * len(rows[0])
    for row in rows:
        for i, v in enumerate(row):
            lengths[i] = max(lengths[i], len(str(v)))

    result = []
    for row in rows:
        values = []
        for i, v in enumerate(row):
            v = str(v)
            padding = (lengths[i] - len(v)) * " "
            values.append(v + padding)
        result.append(values)
    return result


def print_tabulated(rows):
    rows = _tabulate(rows)
    for row in rows:
        print(" ".join(row).rstrip())


@cli.command()
@click.argument("ckb_path")
@click.argument("forum_path")
@click.option("--unknown-path", help="unknown entries csv output path")
def match(ckb_path, forum_path, unknown_path):
    """Match members and forum users

    Optionally write unknown forum users in csv.
    """
    ckb_users = _read_csv(ckb_path)
    forum_users = _read_csv(forum_path)
    m = Matcher(ckb_users)

    matched = []
    for row in forum_users:
        id, uname, _, email, _ = row
        matches = m.match(id, uname, email)

        match_ids = set()
        for reason, m_id in matches:
            match_ids.add(m_id)
        status = "UNKNOWN"
        if match_ids:
            status = "OK"
        if len(match_ids) > 1:
            status = "CONFLICT"

        matches = ",".join("{}={}".format(k, v) for k, v in matches)
        matched.append(tuple(row) + (matches, status))

    now = datetime.date.today()
    print_tabulated(matched)
    max_days = 2 * 365
    unknown = []
    for id, uname, rname, email, last_visit, matches, status in matched:
        if status == "OK":
            continue
        # Prefill delete=1 on users not logged in the last two years
        y, m, d = [int(p) for p in last_visit.split("-")]
        d = datetime.date(y, m, d)
        delta = now - d
        delete = "?"
        if delta.days >= max_days:
            delete = "1"
        unknown.append((id, uname, rname, email, last_visit, delete))

    if unknown_path:
        _write_csv(
            unknown_path,
            ("id", "username", "realname", "email", "last_visit", "delete"),
            unknown,
        )

    print(len(unknown), "unknown entries")


if __name__ == "__main__":
    cli()
