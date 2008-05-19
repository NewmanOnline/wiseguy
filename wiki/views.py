# -*- coding: utf-8 -*-

import logging

from werkzeug import Response

from werkzeug.exceptions import NotFound

from werkzeug.utils import redirect

from utils import create_expose, render, expose_class, render_class

from models import ResourceNotFound

from werkzeug.routing import Map
url_map = Map()

expose = create_expose(url_map)

@expose('/', defaults={'stub':'homepage'})
@expose('/<string:stub>')
@expose('/<string:stub>/r/<int:rev>')
@render('view')
def view(request, stub, rev=None):
    WikiPage = request.models.WikiPage
    User = request.models.User
    if request.session.get('logged_in', False):
        user = User.get_by_username(request.session['username'])
    else:
        user = None
        
    try:
        page = WikiPage.by_id(stub)
    except ResourceNotFound:
        raise NotFound
    
    if rev:
        page = page.revisions[rev]
        revision = True
    else:
        revision = False
    
    return dict(
        page=page,
        user=user,
        revision=revision
    )

@expose('/edit/', defaults={'stub':'homepage'})
@expose('/edit/<string:stub>')
@expose('/edit/<string:stub>/r/<int:rev>')
@render('edit')
def edit(request, stub, rev=None):
    WikiPage = request.models.WikiPage
    # See if the page exists...
    try:
        page = WikiPage.by_id(stub)
    # If not, redirect to the page so that the correct 404 is generated
    except ResourceNotFound:
        return redirect('/%s' % stub)
    
    if rev:
        page = page.revisions[rev]
        revision = True
    else:
        revision = False
    
    return dict(
        page=page,
        revision=revision
    )

@expose('/save/<string:stub>', ['POST'])
def save(request, stub=None):
    WikiPage = request.models.WikiPage
    stub = stub or request.form['stub']
    try:
        page = WikiPage.by_id(stub)
    except ResourceNotFound:
        page = WikiPage()
        page.stub = stub
    
    page.body = request.form['body']
    try:
        page.tags = request.form['tags'].replace(',', ' ').split()
    except KeyError:
        pass
    page = page.save()
    url = request.script_root + '/' + stub
    return redirect(url, 303)
        
@render('not_found')
def not_found(request, response):
    "Displays an edit form and offers to let them create the page"
    WikiPage = request.models.WikiPage
    page = WikiPage(
        stub = request.path.strip('/').split('/', 1)[0] or 'homepage',
        body = None
    )
    return dict(page=page)

@expose('/delete/<string:stub>', ['POST'])
def delete(request, stub=None):
    WikiPage = request.models.WikiPage
    WikiPage.delete(stub)
    url = request.script_root + '/'
    return redirect(url)

@expose('/list/')
@render('list')
def list(request):
    """Lists all the pages, as links"""
    WikiPage = request.models.WikiPage
    pages = WikiPage.get_all()
    return dict(pages=pages)

@expose('/register', ['GET', 'POST'])
@render('register')
def register(request):
    User = request.models.User
    if request.method == 'GET':
        return dict()
    else:
        form = request.form
        errors = {}
        for key in ['username', 'email', 'password']:
            if not form[key]:
                errors[key] = "Please enter the %s" % key
        if not errors:
            if len(User.get_by_username(form['username'])):
                errors['username'] = "That username is already taken"
            if len(User.get_by_email(form['email'])):
                errors['email'] = "That email address is already taken"
        if errors:
            return dict(form_data=form, errors=errors)
        else:
            user = User.create_from_form(form)
            user.save()
            session = request.session
            session['username'] = user.username
            session['logged_in'] = True
            session.save()
            return redirect('/')
    

@expose('/login', ['GET', 'POST'])
@render('login')
def login(request):
    User = request.models.User
    if request.method == 'GET':
        return dict()
    else:
        form = request.form
        errors = {}
        user = User.get_by_username(form['username'])
        if not user:
            errors['username'] = """That username is not in use.  Have you misplet it or would you like to <a href="/register">register</a>?"""
            errors['password'] = """That password would be incorrect if the user existed (which it doesn't)."""
        else:
            if not form['password'] == user.password:
                errors['password'] == """That password is incorrect.  Do you need a <a href="/reminder">reminder</a>?"""
            else:
                session = request.session
                session['username'] = user.username
                session['logged_in'] = True
                session.save()
                return redirect(form.get('from_page', False) or '/')
        return dict(form_data=form, errors=errors)

@expose('/logout')
def logout(request):
    session = request.session
    session['username'] = False
    session['logged_in'] = False
    session.save()
    return redirect('/')


@expose('/<string:stub>/comment', ['POST'])
@render('comment')
def comment(request, stub):
    WikiPage = request.models.WikiPage
    page = WikiPage.by_id(stub)
    form = request.form
    comment = page.save_comment(form['name'], form['email'], form['body'])
    if request.is_xhr:
        # Return a fragment
        return dict(comment=comment)
    else:
        # Clientside javascript mustn't be working.  Redirect back to the page
        return redirect('/%s' % stub)

@expose('/<string:stub>/rating', ['POST'])
@render('rating')
def rating(request, stub):
    WikiPage = request.models.WikiPage
    page = WikiPage.by_id(stub)
    form = request.form
    rating = page.save_rating(form['rating'])
    if request.is_xhr:
        # Return a fragment
        return dict(rating=rating)
    else:
        # Clientside javascript mustn't be working.  Redirect back to the page
        return redirect('/%s' % stub)
    


