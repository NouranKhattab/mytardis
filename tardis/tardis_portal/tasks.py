import logging

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse  # pylint: disable=wrong-import-order

from tardis.celery import tardis_app
from .email import email_user


try:
    from .logging_middleware import LoggingMiddleware
    get_response = lambda _: HttpResponse('')
    LoggingMiddleware(get_response)
except Exception:
    pass

logger = logging.getLogger(__name__)


def init_filters():
    """
    load filters and avoid circular import
    """
    try:
        from .filters import FilterInitMiddleware
        get_response = lambda _: HttpResponse('')
        FilterInitMiddleware(get_response)
    except Exception as e:
        logger.info('filters not loaded for tasks because: %s' % e)


@tardis_app.task(name="tardis_portal.verify_dfos", ignore_result=True)
def verify_dfos(dfos=None, **kwargs):
    from .models import DataFileObject
    dfos_to_verify = dfos or DataFileObject.objects\
                                           .filter(verified=False)
    kwargs['transaction_lock'] = kwargs.get('transaction_lock', True)
    for dfo in dfos_to_verify:
        dfo_verify.apply_async(args=[dfo.id], **kwargs)


@tardis_app.task(name='tardis_portal.ingest_received_files', ignore_result=True)
def ingest_received_files():
    '''
    finds all files stored in temporary storage boxes and attempts to move
    them to their permanent home
    '''
    from .models import StorageBox
    ingest_boxes = StorageBox.objects.filter(Q(attributes__key='type'),
                                             Q(attributes__value='receiving'),
                                             ~Q(master_box=None))
    for box in ingest_boxes:
        sbox_move_to_master.delay(box.id)


@tardis_app.task(name="tardis_portal.autocache", ignore_result=True)
def autocache():
    init_filters()
    from .models import StorageBox
    autocache_boxes = StorageBox.objects.filter(
        Q(attributes__key='autocache'),
        Q(attributes__value__iexact='True'))

    for box in autocache_boxes:
        sbox_cache_files.delay(box.id)


@tardis_app.task(name="tardis_portal.email_user_task", ignore_result=True)
def email_user_task(subject, template_name, context, user):
    email_user(subject, template_name, context, user)


@tardis_app.task(name='tardis_portal.cache_notify', ignore_result=True)
def cache_done_notify(results, user_id, site_id, ct_id, obj_ids):
    user = User.objects.get(id=user_id)
    site = Site.objects.get(id=site_id)
    subject = '[{site}] Cache recall done'.format(site=site.name)
    ct = ContentType.objects.get(id=ct_id)
    objects = [ct.get_object_for_this_type(id=obj_id) for obj_id in obj_ids]
    context = {
        'objects': objects,
        'username': user.username,
    }
    email_user(subject, 'cache_done_email', context, user)
    return "all done"


# "method tasks"
# StorageBox
@tardis_app.task(name="tardis_portal.storage_box.copy_files", ignore_result=True)
def sbox_copy_files(sbox_id, dest_box_id=None):
    init_filters()
    from .models import StorageBox
    sbox = StorageBox.objects.get(id=sbox_id)
    if dest_box_id is not None:
        dest_box = StorageBox.objects.get(id=dest_box_id)
    else:
        dest_box = None
    return sbox.copy_files(dest_box=dest_box)


@tardis_app.task(name="tardis_portal.storage_box.move_files", ignore_result=True)
def sbox_move_files(sbox_id, dest_box_id=None):
    init_filters()
    from .models import StorageBox
    sbox = StorageBox.objects.get(id=sbox_id)
    if dest_box_id is not None:
        dest_box = StorageBox.objects.get(id=dest_box_id)
    else:
        dest_box = None
    return sbox.move_files(dest_box=dest_box)


@tardis_app.task(name="tardis_portal.storage_box.cache_files", ignore_result=True)
def sbox_cache_files(sbox_id):
    init_filters()
    from .models import StorageBox
    sbox = StorageBox.objects.get(id=sbox_id)
    return sbox.cache_files()


@tardis_app.task(name='tardis_portal.storage_box.copy_to_master', ignore_result=True)
def sbox_copy_to_master(sbox_id, *args, **kwargs):
    init_filters()
    from .models import StorageBox
    sbox = StorageBox.objects.get(id=sbox_id)
    return sbox.copy_to_master(*args, **kwargs)


@tardis_app.task(name='tardis_portal.storage_box.move_to_master', ignore_result=True)
def sbox_move_to_master(sbox_id, *args, **kwargs):
    init_filters()
    from .models import StorageBox
    sbox = StorageBox.objects.get(id=sbox_id)
    return sbox.move_to_master(*args, **kwargs)


# DataFile
@tardis_app.task(name="tardis_portal.cache_datafile", ignore_result=True)
def df_cache_file(df_id):
    init_filters()
    from .models import DataFile
    df = DataFile.objects.get(id=df_id)
    return df.cache_file()


# DataFileObject
@tardis_app.task(name='tardis_portal.dfo.move_file', ignore_result=True)
def dfo_move_file(dfo_id, dest_box_id=None):
    init_filters()
    from .models import DataFileObject, StorageBox
    dfo = DataFileObject.objects.get(id=dfo_id)
    if dest_box_id is not None:
        dest_box = StorageBox.objects.get(id=dest_box_id)
    else:
        dest_box = None
    return dfo.move_file(dest_box)


@tardis_app.task(name='tardis_portal.dfo.copy_file', ignore_result=True)
def dfo_copy_file(dfo_id, dest_box_id=None):
    init_filters()
    from .models import DataFileObject, StorageBox
    dfo = DataFileObject.objects.get(id=dfo_id)
    if dest_box_id is not None:
        dest_box = StorageBox.objects.get(id=dest_box_id)
    else:
        dest_box = None
    return dfo.copy_file(dest_box=dest_box)


@tardis_app.task(name='tardis_portal.dfo.cache_file', ignore_result=True)
def dfo_cache_file(dfo_id):
    init_filters()
    from .models import DataFileObject
    dfo = DataFileObject.objects.get(id=dfo_id)
    return dfo.cache_file()


@tardis_app.task(name="tardis_portal.dfo.verify", ignore_result=True)
def dfo_verify(dfo_id, *args, **kwargs):
    init_filters()
    from .models import DataFileObject
    # Get dfo locked for write (to prevent concurrent actions)
    if kwargs.pop('transaction_lock', False):
        with transaction.atomic():
            dfo = DataFileObject.objects.select_for_update().get(id=dfo_id)
            return dfo.verify(*args, **kwargs)
    dfo = DataFileObject.objects.get(id=dfo_id)
    return dfo.verify(*args, **kwargs)
