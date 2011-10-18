import re
from datetime import datetime

class ReplacementField(object):
    # the pattern that will match
    pattern = None
    
    # a global which keeps around the "clean" copy of a text fragment
    old_texts = {}
    
    @classmethod
    def match(self, text):
        ''' Defines whether a field is found. Probably won't need
            overwriting often.
        '''
        if text is None:
            return False
        return re.search(self.pattern, text)
    
    @classmethod
    def install(self, optparser):
        ''' Installs new options into option parser
        '''
        pass
        
    @classmethod
    def replace(self, text_elem, maker):
        ''' remember the old value... if it has already been remembered,
            don't remember again
        '''
        if text_elem not in self.old_texts:
            self.old_texts[text_elem] = text_elem.text

        # update with the changed value
        text_elem.text = self._replace(text_elem.text, maker)
    
    @classmethod
    def restore(self, text_elem):
        ''' put back the values that you found originally
        '''
        if text_elem in self.old_texts:
            text_elem.text = self.old_texts[text_elem]
            del self.old_texts[text_elem]

class PageNumberField(ReplacementField):
    ''' {{#PAGE#}} will be replaced with the current page (starting at 1)
    '''
    
    pattern = r'\{\{\s*#PAGE#\s*\}\}'

    @classmethod
    def _replace(self, text, maker):
        return re.sub(self.pattern, str(maker.slide_number), text)

class NumberOfPagesField(ReplacementField):
    ''' {{#PAGES#}} will be replaced with the total number of slides
    '''
    pattern = r'\{\{\s*#PAGES#\s*\}\}'
    
    @classmethod
    def _replace(self, text, maker):
        return re.sub(self.pattern, str(len(maker.slides)), text)

class DateField(ReplacementField):
    ''' {{#DATE <pattern> #}} will be replaced with current date, 
        formatted as per http://docs.python.org/library/time.html#time.strftime
    '''
    pattern = r'\{\{\s*#DATE\s*([^\}]*)\s*#\s*\}\}'
    
    @classmethod
    def install(self, parser):
        from optparse import OptionGroup
        group = OptionGroup(parser, "Date Field Options: {{#DATE <format>#}}")
        
        datefmt_def = '%x %X'
        date_def = datetime.now().strftime(datefmt_def)
        
        group.add_option("-d", "--date",
            metavar="DATE",
            dest="date",
            default=date_def, 
            help="The date/time to be used. Default: now (%s)" % date_def)
            
        group.add_option("-f", "--dateformat",
            metavar="DATEFORMAT",
            dest="dateformat",
            default=datefmt_def, 
            help="The format to be used for DATE. Default (%s)" % datefmt_def)
            
        parser.add_option_group(group)
    
    @classmethod
    def _replace(self, text, maker):
        
        def repl(m):
            
            return datetime.strptime(maker.options.date, maker.options.dateformat).strftime(m.group(1))
        return re.sub(self.pattern, repl, text)