import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('pilot',Path(__file__).parents[1]/'scripts/recorded_pilot.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class Contract(unittest.TestCase):
    def setUp(self):
        self.d=p.Desktop('http://127.0.0.1:1');self.commands=[]
        self.d.execute=lambda code:self.commands.append(code) or {}
    def test_non_gui_commands_rejected(self):
        with self.assertRaises(ValueError):self.d.action({'action':'shell','text':'touch anything'})
        self.assertEqual(self.commands,[])
    def test_out_of_screen_rejected(self):
        with self.assertRaises(ValueError):self.d.action({'action':'click','x':1280,'y':12})
        self.assertEqual(self.commands,[])
    def test_typing_remains_literal(self):
        self.d.action({'action':'type','text':"');__import__('os').system('false');#"})
        compile(self.commands[0],'<literal GUI input>','exec')
        self.assertIn('p.write(',self.commands[0])
    def test_skill_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):p.Skill(d).load('../anything.md')


class HoloToolParsing(unittest.TestCase):
    def test_xml_tool_arguments_are_data(self):
        spec=importlib.util.spec_from_file_location('server',Path(__file__).parents[1]/'scripts/transformers_server.py')
        server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)
        text='<tool_call><function=desktop><parameter=action>click</parameter><parameter=x>42</parameter><parameter=y>10</parameter></function></tool_call>'
        visible,calls=server.parse_tools(text)
        import json
        self.assertEqual(json.loads(calls[0]['function']['arguments']),{'action':'click','x':42,'y':10})
        self.assertEqual(visible,'')

if __name__=='__main__':unittest.main()
