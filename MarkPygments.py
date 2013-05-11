#coding=utf-8
'''
Usage: 
    MarkPygments.py [options] MDFILE
    MarkPygments.py [options] --local <cssdir> MDFILE 
    MarkPygments.py [options] --config <yamlfile> MDFILE 

Arguments:
    MDFILE                      the markdown file
    -u --username user          your email name
    -p --password pass          your email login password
    -mt --mailto tolist          mailto list
    --theme theme               css style for python syntax  [default: monokai]
    -s --subject subject        email's subject
    --mailserver server         mail server [default: smtp.exmail.qq.com]

Options:
    -h --help                   show this help message and exit
    --version                   show version and exit
    --config yamlfile           config yaml file path (e.g. .config.yaml)
    --local cssdir              use local custom css dir
    -o --output [outhtml]       make output to html file
    -c --cc list                cc list
    --template html             template html 

'''


import os
import re
import codecs
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import markdown
from docopt import docopt
from schema import Schema, And, Or, Use, SchemaError


def log(message, error=False):
    '''终端输出log'''
    color = 31 if error else 32
    print '\x1B[1;{0}m * {1}\x1B[0m'.format(color, message)

def regex():
    '''借用pygments对python语法的实现以及自己实现的正则'''
    from pygments.lexers import PythonLexer
    dict = {}
    lex = PythonLexer()
    token = lex.tokens
    l = ['keywords', 'builtins']
    for i in l:
        dict[i[:2]] = token[i][0][0]
    dict['fu'] = '.*(def)\W+(.*)\((.*)\)'
    dict['cl'] = '.*(?!<span)(class)(?!=)\W+(?!=)(.*)\((.*)\)'
    dict['fm'] = '.*(from)\W+(.*)\W+(import)\W+(.*)'
    dict['im'] = '.*(import)\W\{,\4}(.*)'
    return dict

def sendMail(mailserver, username, password, tolist, subject, msg, cc=[]):

    '''发送邮件'''
    def makeEmail(content):

        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = username
        msg['To'] = ','.join(tolist)
        if cc:
            msg['Cc'] = ','.join(cc) 
        html_part = MIMEText(content, 'html', 'utf-8')
        msg.attach(html_part)
        return msg
    try:

        smtp = smtplib.SMTP()
        log('Connect to {0}'.format(mailserver))
        smtp.connect(mailserver, 25)
        smtp.login(username, password)
        log('Login Success with {0}'.format(username))
        log('To send this Email...')
        if cc:
            smtp.sendmail(username, tolist+cc, makeEmail(msg).as_string())
        else:
            smtp.sendmail(username, tolist, makeEmail(msg).as_string())
        log('Send Success')
    except Exception,e:
        log(e, error=True)

def paserYaml(yamlfile):
    '''解析yaml文件配置'''
    import yaml
    return yaml.load(open(yamlfile)).get('markemail', {})

def check_email(emails):
    '''检查选项是否是邮件格式'''
    print emails
    regex = r'^[_a-z0-9-]+(\.[a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,3})$'
    rst = map(lambda n: True if re.compile(regex).match(n) else False, emails.split(','))
    return True if False not in rst else False

def colorClass():
    '''pygments-css对语法的class对应字典'''
    return dict(
                cl=['k', 'nc', 'nb'],
                fu=['k', 'nf', 'bp'],
                fm=['nd', 'vi', 'nd', 'vi'],
                im=['nd', 'mi'],
                ke=['kd'],
                bu=['vc']
                )


class cssStyle(object):
    '''获取css设置'''
    def __init__(self, style, *args):

        self.style = style
        self.args = args

    def fusionCss(self, csshtml):

        css = '<style type="text/css">'
        css += '.codehilite {border: 2px solid rgb(225, 225, 225)}'
        css += csshtml
        css += '</style>'
        return css

    def local(self, cssdir, theme):
        '''从本地css文件'''
        log('Fetch css from local dir:{0}'.format(cssdir))
        with open('{0}/{1}.css'.format(cssdir, theme)) as f:
            css = f.read().strip()
        return self.fusionCss(css)

    def crawler(self, theme):
        '''去这个网站爬回来'''
        import requests
        log('Fetch css from site:igniteflow.com')
        r = requests.get('http://igniteflow.com/static/css/pygments/{0}.css'.format(theme))
        return self.fusionCss(r.text.strip())

    def main(self):

        return getattr(self, self.style)(*self.args)


class FabricHtml(object):
    
    def __init__(self, md, css):

        self.css = css
        self.md_html = self.makeToHtml(md)

    def makeToHtml(self, md):

        log('Markdown converted into html')
        input_file = codecs.open(md, mode="r", encoding="utf-8")
        text = input_file.read()
        return markdown.markdown(text)

    def AddCssToHtml(self, html, css_html):
        '''增加css的style'''
        ohtml = css_html
        c = html.split('```')
        inc = 0
        ohtml += c[0]
        for inc in range(1, len(c[1:])+1):
            if inc%2:
                ohtml += '<div class="codehilite">'
            else:
                ohtml += '</div>'
            ohtml += c[inc]
            inc += 1
        return ohtml
        
    def makeSpan(self, html, c):
        '''构造span包含符合的语法块'''
        if not html:
            return ''

        return '<span class="{0}">{1}</span>'.format(c, html) 

    def markHtml(self, h):
        '''给html加python语法的颜色css'''
        for k, v in regex().items():
            args = colorClass()[k]
            m = re.compile(r'%s' %v).match(h)
            if m:
                match = m.groups()
                for i in range(len(args)):
                    h = re.sub(match[i], self.makeSpan(match[i], args[i]), h, 1)
        return h

    def main(self, template=''):

        has_css_html = self.AddCssToHtml(self.md_html, self.css)
        return self.pygments(has_css_html) + template

    def pygments(self, html):

        log('Mark span label with python syntax')
        ohtml = ''
        for h in html.split('\n'):
            ohtml += self.markHtml(h)
            ohtml += '\n'
        return ohtml


def checkSchema(schemadict, args):
    '''Pythonic的检查schema'''
    schema = Schema(schemadict)
    try:
        args = schema.validate(args)
    except SchemaError as e:
        raise
        exit(log(e,error=True))
    return args

def main():
    
    args = docopt(__doc__, version='1.0r1')

    isLocal = args.get('--local')
    hasConfig = args.get('--config')
    theme = args.get('--theme')
    if hasConfig:
        checkSchema({
            '--config': And(Use(str), os.path.exists, error='Invalid config format or not exists')
            }, {'--config':hasConfig}
            )
        yamlConfig = paserYaml(hasConfig)
        args.update(yamlConfig)
    args.pop('--config')

    if isLocal:
        checkSchema({
            '--local': And(Use(str), os.path.isdir, lambda n: os.path.exists('{0}/{1}.css'.format(n, theme)),
                error='Invalid custom css dir or hasnot this  theme'),
            }, {'--local':isLocal}
            )
        css_dict = cssStyle('local', isLocal, theme).main()
    else:
        css_dict = cssStyle('crawler', theme).main()
    args.pop('--local')
    args.pop('--theme')
    print args
    args = checkSchema({
        'MDFILE': os.path.exists,
        '--mailserver': Use(str, error='Invalid server format'),
        '--mailto': And(Use(str), lambda n: check_email(n) == True, error='Invalid email format'),
        '--subject': Or(Use(str), Use(unicode), error='Invalid suject format'),
        '--password': Use(str, error='Invalid suject format'),
        '--cc': Or(None, And(Use(str), lambda n: check_email(n) == True), error='Invalid email format'),
        '--output':  Or(False, lambda n: os.path.exists(os.path.dirname('{0}/{1}'.format(os.path.abspath('.'), n))), 
                error='Dir must exists'),
        '--template': Or(None, os.path.exists, error='template must exists'),
        '--username': Use(check_email, error='Invalid username format'), 
        '--help': Or(False, True),
        '--version': Or(False, True)
        }, args)
    do = FabricHtml(args['MDFILE'], css_dict)
    cc = args['--cc'].split(',') if args['--cc'] else []

    if args['--template']:
        with codecs.open(args['--template'], mode="r", encoding="utf-8") as f:
            html_content = do.main(f.read())
    else:
        html_content = do.main()
    if args['--output']:
        with codecs.open(args['--output'], mode="w", encoding="utf-8") as f:
            f.write(html_content)
            exit()

    sendMail(
            args['--mailserver'], 
            args['--username'], 
            args['--password'],
            args['--mailto'].split(','), 
            args['--subject'], 
            html_content, 
            cc
            )

if __name__ == '__main__':  
    
    main()

