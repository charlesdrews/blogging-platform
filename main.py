import os
import urllib
import time
import re

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.datastore.datastore_query import Cursor

import jinja2
import webapp2

from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import images


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
    # auto_now_add means only when object first created
    create_date = ndb.DateTimeProperty(auto_now_add=True)
    # auto_now means everytime an object is updated
    edit_date = ndb.DateTimeProperty(auto_now=True)
    tags = ndb.StringProperty(repeated=True)


class Image(ndb.Model):
    """Models user-uploaded images"""
    user = ndb.UserProperty()
    blob_key = ndb.BlobKeyProperty(required=True)
    filename = ndb.StringProperty(indexed=False)


class MainPage(webapp2.RequestHandler):
    """Handles requests to the app's root page"""    
    def get(self):
        user = users.get_current_user()

        if user:
            login_url = users.create_logout_url(self.request.uri)
            login_text = 'Logout'
        else:
            login_url = users.create_login_url(self.request.uri)
            login_text = 'Login'
        
        user_blogs = Blog.query(Blog.author == user).order(Blog.name)
        all_blogs = Blog.query().order(Blog.name).order(Blog.name)
        
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
    """Handles requests to add a new blog to the datastore""" 
    def post(self):
        if users.get_current_user():
            blog = Blog(parent=global_parent_key())
            blog.name = self.request.get('new_blog_name')
            blog.author = users.get_current_user()
            blog.put()
            time.sleep(1)
            self.redirect('/')
        else:
            self.redirect('/')

    def get(self):
        # if a user tries to create a blog via url, redirect home
        self.redirect('/')


def parsebody(body):
    """Parses blog post body text for images to display inline
       and other links to render in HTML"""
    body = re.sub(r'\n', r'<br>', body)
    # first find images and make them inline
    body = re.sub(r'(\bhttps?://\S+(\.jpg|\.png|\.gif)\b)',
                  r'<img src="\1">', body)
    # then find other links and make them clickable
    body = re.sub(r'(\b(?<!img src=")https?://\S+\b)',
                  r'<a href="\1">\1</a>', body)
    return body


class ViewBlog(webapp2.RequestHandler):
    """Handles requests to view a blog. Passes user and blog info
       to template which posts certain contents only if the current
       user is the blog's author, like links to create/edit posts""" 
    def get(self, blog_id):
        blog = Blog.get_by_id(int(blog_id), global_parent_key())
        selectedtag = self.request.get('tag')
        curs = Cursor(urlsafe=self.request.get('cursor'))

        if selectedtag:
            # if a tag was selected, query only posts w/ that tag
            blog_posts, next_curs, more = BlogPost.query(
                BlogPost.tags == selectedtag,
                ancestor=blog.key).order(
                -BlogPost.create_date).fetch_page(10,
                start_cursor=curs)
        else:
            # else query for all posts from the blog
            blog_posts, next_curs, more = BlogPost.query(
                ancestor=blog.key).order(
                -BlogPost.create_date).fetch_page(10,
                start_cursor=curs)

        for blog_post in blog_posts:
            # trim each post body to 500 characters
            blog_post.body = blog_post.body[0:500]
            # parse body so links & images are handled correctly
            blog_post.body = parsebody(blog_post.body)

        if users.get_current_user():
            login_url = users.create_logout_url(self.request.uri)
            login_text = 'Logout'
        else:
            login_url = users.create_login_url(self.request.uri)
            login_text = 'Login'
              
        # query all posts from the blog again to form tags list
        all_posts = BlogPost.query(ancestor=blog.key)
        tagswdups = []
        for p in all_posts:
            # convert tags from unicode to ascii, add to list
            tagswdups.extend([item.encode('ascii').strip() for item in p.tags])
        # remove duplicates and sort in place
        blogtags = list(set(tagswdups))
        blogtags.sort()
        
        template_values = {
            'user': users.get_current_user(),
            'blog': blog,
            'selectedtag': selectedtag,
            'blog_posts': blog_posts,
            'more': more,
            'login_url': login_url,
            'login_text': login_text,
            'blogtags': blogtags,
        }
        
        if next_curs:
            template_values['cursor'] = next_curs.urlsafe()
           
        template = JINJA_ENVIRONMENT.get_template('blog.html')
        self.response.write(template.render(template_values))
        

class CreatePost(webapp2.RequestHandler):
    """Handles requests to create a new blog post. get() creates
       page with user input form, and post() processes that input"""
    def get(self, blog_id):
        # create the create-post page
        blog = Blog.get_by_id(int(blog_id), global_parent_key())

        if users.get_current_user() == blog.author:
            # if user is blog's author, show create-post page
            login_url = users.create_logout_url(self.request.uri)
            login_text = 'Logout'
            
            template_values = {
                'user': users.get_current_user(),
                'blog': blog,
                'login_url': login_url,
                'login_text': login_text,
            }

            template = JINJA_ENVIRONMENT.get_template('addpost.html')
            self.response.write(template.render(template_values))
        else:
            # if user is not blog's author, redirect to standard blog view
            self.redirect('/blog/%s' % blog.key.id())

    def post(self, blog_id):
        # process the actual blog post creation
        blog = Blog.get_by_id(int(blog_id), global_parent_key())
        
        if users.get_current_user() == blog.author:
            # if user is blog's author, complete creation of blog post
            blog_post = BlogPost(parent=blog.key)
            blog_post.author = users.get_current_user()
            blog_post.title = self.request.get('title')
            blog_post.body = self.request.get('body')
            
            taglist = []
            taglist.extend(self.request.get('tags').split(','))
            blog_post.tags = [ x.strip() for x in taglist ]
            blog_post.put()
            # when done, redirect to blog view
            self.redirect('/blog/%s' % blog.key.id())
        else:
            # if user is not blog's author, redirect w/o creating post
            self.redirect('/blog/%s' % blog.key.id())


class ViewPost(webapp2.RequestHandler):
    """Handles requests to view a post via its permalink"""
    def get(self, blog_id, blog_post_id):
        blog = Blog.get_by_id(int(blog_id), global_parent_key())
        blog_post = BlogPost.get_by_id(int(blog_post_id), blog.key)

        # parse body so links & images are handled correctly
        blog_post.body = parsebody(blog_post.body)

        if users.get_current_user():
            login_url = users.create_logout_url(self.request.uri)
            login_text = 'Logout'
        else:
            login_url = users.create_login_url(self.request.uri)
            login_text = 'Login'

        template_values = {
            'user': users.get_current_user(),
            'blog': blog,
            'post': blog_post,
            'login_url': login_url,
            'login_text': login_text,
        }

        template = JINJA_ENVIRONMENT.get_template('post.html')
        self.response.write(template.render(template_values))


class EditPost(webapp2.RequestHandler):
    """Handles requests to edit posts. get() creates page with
       user input form, and post() processes that input"""
    def get(self, blog_id, blog_post_id):
        # create the edit-post page
        blog = Blog.get_by_id(int(blog_id), global_parent_key())
        blog_post = BlogPost.get_by_id(int(blog_post_id), blog.key)
        
        if users.get_current_user() == blog_post.author:
            # if user is post's author, show edit-post page
            login_url = users.create_logout_url(self.request.uri)
            login_text = 'Logout'
            
            template_values = {
                'user': users.get_current_user(),
                'blog': blog,
                'post': blog_post,
                'login_url': login_url,
                'login_text': login_text,
            }

            template = JINJA_ENVIRONMENT.get_template('editpost.html')
            self.response.write(template.render(template_values))
        else:
            # if user is not post's author, redirect to standard blog view
            self.redirect('/blog/%s' % blog.key.id())

    def post(self, blog_id, blog_post_id):
        # process the actual edit
        blog = Blog.get_by_id(int(blog_id), global_parent_key())
        blog_post = BlogPost.get_by_id(int(blog_post_id), blog.key)
        
        if users.get_current_user() == blog_post.author:
            # if user is post's author, continue processing the edit
            blog_post.title = self.request.get('new_title')
            blog_post.body = self.request.get('new_body')

            taglist = []
            taglist.extend(self.request.get('tags').split(','))
            blog_post.tags = [ x.strip() for x in taglist ]
            blog_post.put()

            self.redirect('/blog/%s' % blog.key.id())
        else:
            # if user is not post's author, redirect to standard blog view
            self.redirect('/blog/%s' % blog.key.id())


class ImagesHandler(webapp2.RequestHandler):
    """Handles requests to view the page with the upload image form
       and a list of previously uploaded images w/ permalinks"""
    def get(self):
        upload_url = blobstore.create_upload_url('/upload')

        if users.get_current_user():
            # if user is logged in, show upload image page
            images = Image.query(Image.user == users.get_current_user(),
                        ancestor=global_parent_key())
                       
            login_url = users.create_logout_url(self.request.uri)
            login_text = 'Logout'

            template_values = {
                'user': users.get_current_user(),
                'upload_url': upload_url,
                'images': images,
                'login_url': login_url,
                'login_text': login_text,
            }

            template = JINJA_ENVIRONMENT.get_template('images.html')
            self.response.write(template.render(template_values))
        else:
            # if user is not logged in, redirect to home
            self.redirect('/')


class UploadHandler(blobstore_handlers.BlobstoreUploadHandler):
    """Handles request to upload image to datastore""" 
    def post(self):
        # process the upload
        upload_files = self.get_uploads('image')
        blob_info = upload_files[0]
        image = Image(parent=global_parent_key(),
                      user = users.get_current_user(),
                      blob_key = blob_info.key(),
                      filename = blob_info.filename)
        image.put()
        time.sleep(1)
        self.redirect('/images')


class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
    """Handles requests to view a user-uploaded image"""
    def get(self, blob_key, filename):
        # filename not used directly; but it's presence at the
        # end of the permalink means when a user puts that
        # permalink in the body of a post, the link-parsing
        # function will recognize it (from the filename extension)
        # and wrap it in a <img> tag
        blob_key = str(urllib.unquote(blob_key))
        if not blobstore.get(blob_key):
            self.error(404)
        else:
            self.send_blob(blobstore.BlobInfo.get(blob_key))


application = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/createblog', CreateBlog),
    ('/blog/(\d+)', ViewBlog),
    ('/createpost/(\d+)', CreatePost),
    ('/post/(\d+)/(\d+)', ViewPost),
    ('/editpost/(\d+)/(\d+)', EditPost),
    ('/images', ImagesHandler),
    ('/upload', UploadHandler),
    ('/serve/([^/]+)/([^/]+)', ServeHandler),
], debug=True)
