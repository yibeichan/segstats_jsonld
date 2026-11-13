# pytest puts the directory of this file first on sys.path, so the tests in
# tests/ import segstats_jsonld from this checkout and not from an installed
# copy, whichever directory or command pytest is started from.
