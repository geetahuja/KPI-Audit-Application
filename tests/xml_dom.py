"""Test-only DOM bridge for exercising the browser XLSX parser without a browser."""
import sys,json,xml.etree.ElementTree as ET
def convert(n):
    return {'name':n.tag.split('}')[-1],'attrs':n.attrib,'text':n.text or '', 'tail':n.tail or '', 'children':[convert(c) for c in n]}
try:print(json.dumps(convert(ET.fromstring(sys.stdin.read()))))
except ET.ParseError:print(json.dumps({'name':'parsererror','attrs':{},'text':'Invalid XML','tail':'','children':[]}))
