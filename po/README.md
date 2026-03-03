# Translations

Translations are managed on Transifex:

https://app.transifex.com/danielnylander/freeipa-manager/

## Contributing

1. Sign up at [Transifex](https://www.transifex.com/)
2. Join the project and request your language
3. Translate via the web editor

## For developers

Pull translations:

```bash
tx pull --minimum-perc 20
```

Push updated source strings:

```bash
xgettext --language=Python --keyword=_ --keyword=N_ \
  --output=po/freeipa-manager.pot \
  $(cat po/POTFILES.in)
tx push -s
```
