"""Main views for memex-explorer application"""
from __future__ import absolute_import, division, print_function

#  IMPORTS 
# =========

# Standard Library
# ----------------

import os
import logging
import json
import datetime as dt
import subprocess

# Third-party Libraries 
# ---------------------

from flask import (redirect, flash, render_template, request, url_for,
                   send_from_directory, jsonify, session, abort)
from werkzeug import secure_filename
from webhelpers import text

from blaze import resource, discover, Data, into, compute
from pandas import DataFrame
from bokeh.plotting import ColumnDataSource

# Local Imports
# -------------

from . import app, db
from .models import Crawl, DataSource, Dashboard, Plot, Project, Image, ImageSpace, \
                    DataModel
from .db_api import (get_project, get_crawl, get_crawls, get_dashboards, get_data_source,
                     get_images, get_image, get_matches, db_add_crawl, get_plot,
                     db_init_ache, get_crawl_model, get_models, get_image_space)

from .rest_api import api

from .forms import CrawlForm, MonitorDataForm, PlotForm, ContactForm, \
                    DashboardForm, ProjectForm, DataModelForm
from .mail import send_email

from .config import ADMINS, DEFAULT_MAIL_SENDER, BASEDIR, SEED_FILES, \
                    CONFIG_FILES, MODEL_FILES, CRAWLS_PATH

from .auth import requires_auth
from .plotting import plot_builder
from .crawls import AcheCrawl, NutchCrawl


from .viz.domain import Domain
from .viz.harvest import Harvest
from .viz.harvest_rate import HarvestRate

from .viz.plot import plot_exists
# from .viz.termite import Termite


# Dictionary of crawls by key(project_name-crawl_name)
CRAWLS_RUNNING = {}


@app.context_processor
def context():
    """Inject some context variables useful across templates.
    See http://flask.pocoo.org/docs/0.10/templating/#context-processors
    """

    context_vars = {}

    if request.view_args and 'project_name' in request.view_args:
        project_name = request.view_args['project_name']
        project = get_project(project_name)
        if not project:
            return {}
            # flash("Project '%s' was not found." % project_name, 'error')
            # abort(404)

        crawls = get_crawls(project.id)
        dashboards = get_dashboards(project.id)
        models = get_models()
        image_spaces = get_image_space(project.id)


        context_vars.update(dict(
            project=project, crawls=crawls, dashboards=dashboards, \
            models=models, image_spaces=image_spaces))

    # All pages should (potentially) be able to present all projects
    context_vars.update(projects=Project.query.all())

    return context_vars


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def application_error(e):
    # TODO
    # http://flask.pocoo.org/docs/0.10/errorhandling/#application-errors

    # sender = DEFAULT_MAIL_SENDER
    # send_email(subject=subject, sender=sender, recipients=ADMINS, text_body=text_body, html_body=text_body)
    return render_template('500.html'), 500


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(BASEDIR, 'static'),
                               'favicon.ico', mimetype='image/x-icon')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about/')
def about_page():
    return render_template('about.html')


# Project
# -----------------------------------------------------------------------------

@app.route('/<project_name>')
def project(project_name):

    # return render_template('project.html', project=project, crawls=crawls,
    #                                        dashboards=dashboards)

    # `project`, `crawls`, and `dashboards` handled by the context processor.
    #   See `context() defined above.`
    return render_template('project.html')


@app.route('/add_project', methods=['GET', 'POST'])
def add_project():
    form = ProjectForm(request.form)

    if form.validate_on_submit():
        project = Project(name=form.name.data, description=form.description.data, \
                        icon=form.icon.data)
        db.session.add(project)
        db.session.commit()
        flash("Project '%s' was successfully registered" % project.name, 'success')
        return redirect(url_for('project', project_name=project.name))

    return render_template('add_project.html', form=form)


# Crawl
# -----------------------------------------------------------------------------

@app.route('/<project_name>/add_crawl', methods=['GET', 'POST'])
def add_crawl(project_name):
    form = CrawlForm()
    if form.validate_on_submit():
        seed_filename = secure_filename(form.seeds_list.data.filename)
        form.seeds_list.data.save(SEED_FILES + seed_filename)
        # TODO allow upload configuration
        #config_filename = secure_filename(form.config.data.filename)
        #form.config.data.save(CONFIG_FILES + config_filename)
        project = get_project(project_name)
        crawl = db_add_crawl(project, form, seed_filename)
        subprocess.Popen(['mkdir', os.path.join(CRAWLS_PATH, crawl.name)])

        if crawl.crawler == 'ache':
            db_init_ache(project, crawl)

        else: 
            #TODO add db_init_nutch
            pass

        flash('%s has successfully been registered!' % form.name.data, 'success')
        return redirect(url_for('crawl', project_name=get_project(project_name),
                                         crawl_name=form.name.data))

    return render_template('add_crawl.html', form=form)


@app.route('/<project_name>/add_model', methods=['GET', 'POST'])
def add_model(project_name):
    form = DataModelForm()
    if form.validate_on_submit():
        registered_model = DataModel.query.filter_by(name=form.name.data).first()
        if registered_model:
            flash('Data model name already exists, please choose another name', 'error')
            return render_template('add_data_model.html', form=form)
        files = request.files.getlist("files")
        os.mkdir(MODEL_FILES + form.name.data)
        for x in files:
            x.save(MODEL_FILES + form.name.data + '/' + x.filename)
        model = DataModel(name=form.name.data,
                          filename=MODEL_FILES + form.name.data)

        db.session.add(model)
        db.session.commit()
        flash('Model has successfully been registered!', 'success')
        return redirect(url_for('project', 
                                project_name=get_project(project_name).name))

    return render_template('add_data_model.html', form=form)


@app.route('/<project_name>/crawls')
def crawls(project_name):
    return render_template('crawls.html')


@app.route('/<project_name>/crawls/<crawl_name>')
def crawl(project_name, crawl_name):
    project = get_project(project_name)
    crawl = get_crawl(crawl_name)

    if not project:
        flash("Project '%s' was not found." % project_name, 'error')
        abort(404)
    elif not crawl:
        flash("Crawl '%s' was not found." % crawl_name, 'error')
        abort(404)

    return render_template('crawl.html', crawl=crawl)


@app.route('/<project_name>/crawls/<crawl_name>/run', methods=['POST'])
def run_crawl(project_name, crawl_name):
    key = project_name + '-' + crawl_name
    if CRAWLS_RUNNING.has_key(key):
        return "Crawl is already running."
    else:
        crawl = get_crawl(crawl_name)
        seeds_list = crawl.seeds_list
        if crawl.crawler=="ache":
            model = get_crawl_model(crawl)
            crawl_instance = AcheCrawl(crawl_name=crawl.name, seeds_file=seeds_list, model_name=model.name,
                                       conf_name=crawl.config)
            pid = crawl_instance.start()
            CRAWLS_RUNNING[key] = crawl_instance
            return "Crawl %s running" % crawl.name
        elif crawl.crawler=="nutch":
            crawl_instance = NutchCrawl(seed_dir=seeds_list, crawl_dir=crawl.name)
            pid = crawl_instance.start()
            CRAWLS_RUNNING[key] = crawl_instance
            return "Crawl %s running" % crawl.name
        else:
            abort(400)


@app.route('/<project_name>/crawls/<crawl_name>/stop', methods=['POST'])
def stop_crawl(project_name, crawl_name):
    key = project_name + '-' + crawl_name
    crawl_instance = CRAWLS_RUNNING.get(key)
    if crawl_instance is not None:
        crawl_instance.stop()
        del CRAWLS_RUNNING[key]
        return "Crawl stopped"
    else:
        abort(400)


@app.route('/<project_name>/crawls/<crawl_name>/refresh', methods=['POST'])
def refresh(project_name, crawl_name):

    project = get_project(project_name)

    ### Domain
    domain_plot = get_plot(crawl_name + "-domain")
    crawled = get_data_source(project.id, crawl_name + "-crawledpages")
    relevant = get_data_source(project.id, crawl_name + "-relevantpages")
    frontier = get_data_source(project.id, crawl_name + "-frontierpages")
    domain_sources = dict(crawled=crawled, relevant=relevant, frontier=frontier)

    domain = Domain(domain_sources, domain_plot)
    domain.push_to_server()
    ###


    ### Harvest
    harvest_plot = get_plot(crawl_name + "-harvest")
    harvest_source = get_data_source(project.id, crawl_name + "-harvest")

    harvest = Harvest(harvest_source, harvest_plot)
    harvest.push_to_server()
    ###

    return "pushed"


@app.route('/<project_name>/crawls/<crawl_name>/dashboard')
def crawl_dash(project_name, crawl_name):

    project = get_project(project_name)
    crawl = get_crawl(crawl_name)

    key = project_name + '-' + crawl_name
    crawl_instance = CRAWLS_RUNNING.get(key)

    if crawl.crawler == 'ache':
        # TODO put all this is a function create_ache_dashboard

        ### Domain
        domain_plot = get_plot(crawl_name + "-domain")
        if domain_plot.autoload_tag and plot_exists(domain_plot):
            domain_tag = domain_plot.autoload_tag

        else:
            crawled = get_data_source(project.id, crawl_name + "-crawledpages")
            relevant = get_data_source(project.id, crawl_name + "-relevantpages")
            frontier = get_data_source(project.id, crawl_name + "-frontierpages")
            domain_sources = dict(crawled=crawled, relevant=relevant, frontier=frontier)

            domain = Domain(domain_sources, domain_plot)
            domain_tag = domain.create_and_store()
        ###


        ### Harvest
        harvest_plot = get_plot(crawl_name + "-harvest")
        if harvest_plot.autoload_tag:
            harvest_tag = harvest_plot.autoload_tag

        else:
            harvest_source = get_data_source(project.id, crawl_name + "-harvest")
            harvest = Harvest(harvest_source, harvest_plot)
            harvest_tag = harvest.create_and_store()
        ###

        return render_template('dash.html', plots=[domain_tag, harvest_tag], crawl=crawl)

    else:
        abort(400)



@app.route('/<project_name>/crawls/<crawl_name>/status', methods=['GET'])
def status_crawl(project_name, crawl_name):
    key = project_name + '-' + crawl_name
    crawl_instance = CRAWLS_RUNNING.get(key)
    if crawl_instance is not None:
        return crawl_instance.status()
    else:
        return "Stopped"



# Plot & Dashboard
# -----------------------------------------------------------------------------

@app.route('/<project_name>/add_dashboard', methods=['GET', 'POST'])
def add_dashboard(project_name):
    project = Project.query.filter_by(name=project_name).first()
    crawls = Crawl.query.filter_by(project_id=project.id)
    dashboards = Dashboard.query.filter_by(project_id=project.id)
    form = DashboardForm(request.form)

    if form.validate_on_submit():
        data = Dashboard(name=form.name.data, description=form.description.data, \
                        project_id=project.id)
        db.session.add(data)
        db.session.commit()
        flash("Dashboard '%s' was successfully registered" % form.name.data, 'success')
        return redirect(url_for('dash', project_name=project.name, \
                        dashboard_name=form.name.data))

    return render_template('add_dashboard.html', project=project, crawls=crawls,
                            form=form, dashboards=dashboards)


@app.route('/<project_name>/dashboards/<dashboard_name>')
def dash(project_name, dashboard_name):
    project = Project.query.filter_by(name=project_name).first()
    crawls = Crawl.query.filter_by(project_id=project.id)
    dashboards = Dashboard.query.filter_by(project_id=project.id)
    dashboard = Dashboard.query.filter_by(name=dashboard_name).first()
    plots = Plot.query.filter_by(project_id=project.id)
    if not dashboard:
        flash("Dashboard '%s' was not found." % dashboard_name, 'error')
        abort(404)
    elif not project:
        flash("Project '%s' was not found." % project_name, 'error')
        abort(404)
    elif dashboard.project_id != project.id:
        flash("Dashboard is not part of project '%s'." % project_name, 'error')
        abort(404)

    return render_template('dash.html', project=project, crawls=crawls, \
                           dashboards=dashboards, dashboard=dashboard, plots=plots)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm(request.form)
    crawls = Crawl.query.all()

    if form.validate_on_submit():
        subject = ' -- '.join([form.issue.data, form.name.data])
        sender = DEFAULT_MAIL_SENDER
        text_body = form.description.data
        send_email(subject=subject, sender=sender, recipients=ADMINS,
                   text_body=text_body, html_body=text_body)
        flash('Thank you for contacting us! We will be in touch shortly.', 'success')
        return redirect(url_for('index'))

    return render_template('contact.html', form=form)


# Compare (Image Space)
# ------------------------------------------------------------------------

@app.route('/<project_name>/image_space/<image_space_name>/<image_name>/compare/')
def compare(project_name, image_space_name, image_name):

    project = get_project(project_name)
    image_space = ImageSpace.query.filter_by(name=image_space_name).first()
    # TODO change to query by image_space. Requires db changes.
    images = get_images()
    img = get_image(image_name)
    exif_info = dict(zip(('EXIF_BodySerialNumber', 'EXIF_LensSerialNumber',
              'Image_BodySerialNumber', 'MakerNote_InternalSerialNumber',
              'MakerNote_SerialNumber', 'MakerNote_SerialNumberFormat'),

             (img.EXIF_BodySerialNumber, img.EXIF_LensSerialNumber,
              img.Image_BodySerialNumber, img.MakerNote_InternalSerialNumber,
              img.MakerNote_SerialNumber, img.MakerNote_SerialNumberFormat)))

    # serial_matches = get_info_serial(img.EXIF_BodySerialNumber)
    # full_match_paths = [app.config['STATIC_IMAGE_DIR'] + x.img_file for x in serial_matches
    #                                                                  if x.Uploaded != 1]
    # internal_matches = [(x.split('/static/')[-1], x.split('/')[-1])
    #                         for x in full_match_paths]

    internal_matches = get_matches(project.id, img.img_file)
    for x in internal_matches:
        if (img.id, x.id) in app.MATCHES:
            x.match = "true"
        else:
            x.match = "false"

    # if img.EXIF_BodySerialNumber:
    #     external_matches = lost_camera_retreive(img.EXIF_BodySerialNumber)
    # else:
    #     external_matches = []

    return render_template('compare.html', image=img, exif_info=exif_info, image_space=image_space,
                            internal_matches=internal_matches,
                            # external_matches=external_matches
                             )

@app.route('/static/<image_space_name>/images/<image_name>')
def image_source(image_space_name, image_name):
    img_dir = os.path.join(BASEDIR, 'static', image_space_name, 'images_blurred/')
    img_filename = image_name

    return send_from_directory(img_dir, img_filename)


@app.route('/<project_name>/image_space/<image_space_name>/')
def image_table(project_name, image_space_name):
    #images = get_images_in_space(project_name, image_space_name)
    project = get_project(project_name)
    image_space = ImageSpace.query.filter_by(name=image_space_name).first()
    images = get_images()
    return render_template('image_table.html', images=images, project=project, image_space=image_space)


@app.route('/<project_name>/image_space/<image_space_name>/<image_name>')
def inspect(project_name, image_space_name, image_name):
    img = get_image(image_name)
    image_space = ImageSpace.query.filter_by(name=image_space_name).first()

    exif_info = dict(zip(('EXIF_BodySerialNumber', 'EXIF_LensSerialNumber',
              'Image_BodySerialNumber', 'MakerNote_InternalSerialNumber',
              'MakerNote_SerialNumber', 'MakerNote_SerialNumberFormat'),

             (img.EXIF_BodySerialNumber, img.EXIF_LensSerialNumber,
              img.Image_BodySerialNumber, img.MakerNote_InternalSerialNumber,
              img.MakerNote_SerialNumber, img.MakerNote_SerialNumberFormat)))

    return render_template('inspect.html', image=img, image_space=image_space, exif_info=exif_info)

