cd ~/nk/g36 || exit 1
python3 - <<'PY'
s=open('nkvt.c').read()
i=s.index('static int xBestIndex'); j=s.index('\n}\n',i)
body=s[i:j]; print(body[-420:])
PY
