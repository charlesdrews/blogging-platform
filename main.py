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


def global_parent_key():
    """Constructs a Datastore key to be used as a parent for all blogs.
       This allows the app to query a list of all blogs via an
       ancestor query, which ensures strong consistency"""
    return ndb.Key('Global_Parent', 'charlesdrews')


class Blog(ndb.Model):
    """Models a blog with name and author"""
    name = ndb.StringProperty()
    author = ndb.UserProperty()


class BlogPost(ndb.Model):
    """Models a blog post with author, title, body, and date"""
    author = ndb.UserProperty()
    title = ndb.StringProperty(indexed=False)
    body = ndb.StringProperty(indexed=False)
    create_date = ndb.DateTimeProperty(auto_now_add=True)
    edit_date = ndb.DateTimeProperty(auto_now_add=True)


class MainPage(webapp2.RequestHandler):
    
    def get(self):
        user = users.get_current_user()

        if user:
            login_url = users.create_logout_url(self.request.uri)
            login_text = 'Logout'
        else:
            login_url = users.create_login_url(self.request.uri)
            login_text = 'Login'
        
        user_blogs = Blog.query(Blog.author == user) #.order(Blog.name)
        all_blogs = Blog.query().order(Blog.name)
        
        template_values = {
            'user': user,
            'user_blogs': user_blogs,
            'all_blogs': all_blogs,
            'login_url': login_url,
            'login_text': login_text
        }
        
        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))


class CreateBlog(webapp2.RequestHandler):
    
    def post(self):
        if users.get_current_user():
            blog = Blog(parent=global_parent_key())
            blog.name = self.request.get('new_blog_name')
            blog.author = users.get_current_user()
            blog.put()
            self.redirect('/editblog')
        else:
            self.redirect('/')

    def get(self):
            self.redirect('/')


class EditBlog(webapp2.RequestHandler):
    
    def post(self):
        if users.get_current_user():
            blog_url_key = self.request.get('blog_url_key')
            blog_key = ndb.Key(urlsafe=blog_url_key)
            blog = blog_key.get()
            blog_posts = BlogPost.query(ancestor=blog_key)
            login_url = users.create_logout_url(self.request.uri)
            login_text = 'Logout'
            
            template_values = {
                'user': users.get_current_user(),
                'blog': blog,
                'blog_posts': blog_posts,
                'login_url': login_url,
                'login_text': login_text
            }

            template = JINJA_ENVIRONMENT.get_template('edit.html')
            self.response.write(template.render(template_values))
            #self.redirect('/editblog')
# apparently not OK to have redirects after a handler...
        else:
            self.redirect('/')

    def get(self):
            self.redirect('/')


class CreatePost(webapp2.RequestHandler):
    
    def post(self):
        if users.get_current_user():
            blog_url_key = self.request.get('blog_url_key')
            blog_key = ndb.Key(urlsafe=blog_url_key)
            blog = blog_key.get()

            blog_post = BlogPost(parent=blog_key)
            blog_post.author = users.get_current_user()
            blog_post.title = self.request.get('title')
            blog_post.body = self.request.get('body')
            blog_post.put()
            #self.redirect('/blog')
        else:
            self.redirect('/')

    def get(self):
            self.redirect('/')


class ShowBlog(webapp2.RequestHandler):

    def get(self):
        blog_url_key = self.request.get('blog_url_key')
        blog_key = ndb.Key(urlsafe=blog_url_key)
        blog = blog_key.get()
        blog_posts = BlogPost.query(ancestor=blog_key).order(-BlogPost.create_date)

        template_values = {
            'blog_name': blog.name,
            'blog_posts': blog_posts
        }

        template = JINJA_ENVIRONMENT.get_template('blog.html')
        self.response.write(template.render(template_values))


class ShowPost(webapp2.RequestHandler):

    def get(self):
        post_url_key = self.request.get('post_url_key')
        post_key = ndb.Key(urlsafe=post_url_key)
        post = post_key.get()
        blog = post.key.parent().get()

        template_values = {
            'blog': blog,
            'post': post
        }

        template = JINJA_ENVIRONMENT.get_template('post.html')
        self.response.write(template.render(template_values))


application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/createblog', CreateBlog),
    ('/editblog', EditBlog),
    ('/createpost', CreatePost),
    ('/blog', ShowBlog),
    ('/post', ShowPost),
], debug=True)
