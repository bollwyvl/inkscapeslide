import re

class ReplacementField(object):
    pattern = None
    old_texts = {}
    
    @classmethod
    def match(self, text):
        if text is None:
            return False
        return re.search(self.pattern, text)
        
    @classmethod
    def replace(self, text_elem, maker):
        # remember the old value... if it has already been remembered,
        # don't remember again
        if text_elem not in self.old_texts:
            self.old_texts[text_elem] = text_elem.text

        # update with the changed value
        text_elem.text = self._replace(text_elem.text, maker)
    
    @classmethod
    def restore(self, text_elem):
        # put back the values that you found originally
        if text_elem in self.old_texts:
            text_elem.text = self.old_texts[text_elem]
            del self.old_texts[text_elem]

class PageNumberField(ReplacementField):
    pattern = r'\{\{\s*#PAGE#\s*\}\}'

    @classmethod
    def _replace(self, text, maker):
        return re.sub(self.pattern, str(maker.slide_number), text)

class NumberOfPagesField(ReplacementField):
    pattern = r'\{\{\s*#PAGES#\s*\}\}'
    
    @classmethod
    def _replace(self, text, maker):
        return re.sub(self.pattern, str(len(maker.slides)), text)

class DateField(ReplacementField):
    pattern = r'\{\{\s*#DATE\s*([^\}]*)\s*#\s*\}\}'
    
    @classmethod
    def _replace(self, text, maker):
        from datetime import datetime
        fmt = re.search(self.pattern, text).group(1)
        return re.sub(self.pattern, datetime.now().strftime(fmt), text)