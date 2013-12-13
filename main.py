import os
import urllib

from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class Blog(ndb.Model):
    """Models a blog with name and author"""
    name = ndb.StringProperty(indexed=False)
    author = ndb.UserProperty()


class BlogPost(ndb.Model):
    """Models a blog post belonging to a blog
       and having an author, title, body, and date
    """
    blog = ndb.StringProperty(indexed=False)
    author = ndb.UserProperty()
    title = ndb.StringProperty(indexed=False)
    body = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)


class MainPage(webapp2.RequestHandler):
    
    def get(self):
        user = users.get_current_user()

        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
        
        user_blogs = Blog.query(Blog.author == user)

        template_values = {
            'user': user,
            'user_blogs': user_blogs,
            'url': url,
            'url_linktext': url_linktext
        }
        
        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))

application = webapp2.WSGIApplication([
    ('/', MainPage),
], debug=True)
