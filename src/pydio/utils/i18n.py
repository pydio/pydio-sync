# -*- coding: utf-8 -*-

import os, sys
import locale
import gettext
from pathlib import *

# Change this variable to your app name!
#  The translation files will be under
#  @LOCALE_DIR@/@LANGUAGE@/LC_MESSAGES/@APP_NAME@.mo
APP_NAME = "pydio"
if getattr(sys, 'frozen', False):
    LOCALE_DIR = str((Path(sys._MEIPASS)) / 'res' / 'i18n' )
else:
    LOCALE_DIR = str(Path(__file__).parent.parent / 'res' / 'i18n')


# This is ok for maemo. Not sure in a regular desktop:

# Now we need to choose the language. We will provide a list, and gettext
# will use the first translation available in the list
#
#  In maemo it is in the LANG environment variable
#  (on desktop is usually LANGUAGES)
def get_languages():
    DEFAULT_LANGUAGES = os.environ.get('LANG', '').split(':')
    DEFAULT_LANGUAGES += ['en_US']

    languages = []
    lc, encoding = locale.getdefaultlocale()
    if lc:
        languages = [lc]

    # Concat all languages (env + default locale),
    #  and here we have the languages and location of the translations
    languages += DEFAULT_LANGUAGES
    return languages


languages = get_languages()
mo_location = LOCALE_DIR
gettext.install(True, localedir=None, unicode=1)
gettext.find(APP_NAME, mo_location)
gettext.textdomain (APP_NAME)
gettext.bind_textdomain_codeset(APP_NAME, "UTF-8")
language = gettext.translation(APP_NAME, mo_location, languages=languages, fallback=True)

"""
Utilitary to transform HTML strings to PO compatible strings.
Process is the following
* In PY files, declare the following import, and use _('')
    from pydio.utils import i18n
    _ = i18n.language.ugettext
* In HTML files, Use {{_('')}} function.
    Make sure to assign the function to the scope:
    > $scope._ = window.translate;

* Update the content of html_strings.py
    > pydio-sync-agent --extract_html=extract
    This will update the content of res/i18n/html_strings.py with all html strings in a python format

* Update the pydio.pot file by using gettext standard command (from the root of pydio source folder)
    > xgettext --language=Python --keyword=_ --output=res/i18n/pydio.pot `find . -name "*.py"`

* Merge its content into existing PO files using msgmerge. For example for french:
    > msgmerge -vU fr.po pydio.pot

* To add a new language, use msginit
    > msginit --input=pydio.pot --locale=fr_FR --output-file=fr.po

* Manually update PO files with missing strings
* Compile PO to MO files using msgfmt
    > msgfmt fr.po --output-file fr/LC_MESSAGES/pydio.mo

* Compile PO to JSON file using application tool
    > pydio-sync-agent --extract_html=compile
    This will update the file ui/res/i18n.js that is loaded by the UI and contains all languages.


"""
class PoProcessor:

    def __init__(self):
        pass

    def po_to_json(self, glob_expr, dest_file):

        import json
        import polib
        import glob

        files = glob.glob(glob_expr)
        dest = open(dest_file, "w")
        dest.write('window.PydioLangs={};\n')

        for srcfile in files:

            print("INFO: converting %s to %s" % (srcfile, dest_file))

            xlate_map = {}

            po = polib.pofile(srcfile, autodetect_encoding=False, encoding="utf-8", wrapwidth=-1)
            for entry in po:
                if entry.obsolete or entry.msgstr == '' or entry.msgstr == entry.msgid:
                    continue

                xlate_map[entry.msgid] = entry.msgstr

            lang = os.path.basename(srcfile).replace(".po", "")
            dest.write('window.PydioLangs["%s"]=' % lang)
            dest.write(json.dumps(xlate_map, sort_keys= True))
            dest.write(';\n')

        dest.close()


    def extract_html_strings(self,file_name):
        import re

        groups = []
        with open(file_name) as fp:
            for line in fp:
                mo = re.findall("_\('(.*?)'", line)
                if mo:
                    groups += mo
        return groups


    def extract_all_html_strings(self, root_html, output_file):

        import glob

        strings = []
        files = glob.glob(root_html + '/*.html')
        for html_file in files:
            strings += self.extract_html_strings(html_file)

        index = 1
        with open(output_file, 'w') as fp:
            fp.write('def _(a_string): return a_string\n')
            for a_string in strings:
                fp.write('var_%i=_(\'%s\')\n' % (index, a_string,))
                index += 1

        return len(strings)


