const zotero = 'https://api.zotero.org/users/4809962/';
const api_key = 'hTvqMYvC4Bjhm4xGHqyCTSWv';

var global_hash = new Map();
var global_dataset = new Array();

$(document).ready(function () {
  console.log("Hey! If you see a CORS policy error it is due to Zotero server.");
  $.ajax({
    type: 'HEAD',
    url: zotero + 'items',
    crossDomain: true,
    beforeSend: function (request) {
      request.setRequestHeader('Zotero-API-Key', api_key);
      request.setRequestHeader('If-Modified-Since-Version', localStorage['version']);
    },
    success: function (response) {
      load_from_zotero();
    },
    error: function (response) {
      load_from_local_storage();
    }
  });
});

$('#request').on('keyup', function () {
  show_list($('#request').val() ? $('#request').val() : '');
});

$(document).on('click', '.tag', function (e) {
  e.preventDefault();
  $('#request').val($(e.target).text() + ' ');
  show_list($('#request').val() ? $('#request').val() : '');
});

// Loaders

function load_from_zotero() {
  $.ajax({
    url: zotero + 'publications/items?sort=date',
    crossDomain: true,
    dataType: 'json',
    beforeSend: function (request) {
      request.setRequestHeader('Zotero-API-Key', api_key);
    },
    success: function (data, status, response) {
      process_publications(data, response.getResponseHeader('Last-Modified-Version'));
    },
    error: function (response) {
      show_error('No data');
    }
  });
}

function load_from_local_storage() {
  if (localStorage['dataset']) {
    global_dataset = JSON.parse(localStorage['dataset']);
    var i = 0;
    global_dataset.forEach(function (element) {
      global_hash[element['key']] = i;
      i++;
    });
    show_list('');
  } else {
    load_from_zotero();
  }
}

// Data processing

function process_publications(data, version) {
  data.forEach(function (item) {
    var element = item['data'];
    if (element['itemType'] != 'attachment') {
      element['tags'] = new Array();
      global_hash[element['key']] = global_dataset.push(element) - 1;
      process_tags(element['key']);
    }
  });
  localStorage['dataset'] = JSON.stringify(global_dataset);
  localStorage['version'] = version;
  show_list('');
}

function process_tags(key) {
  $.ajax({
    url: zotero + 'items/' + key + '/tags',
    crossDomain: true,
    dataType: 'json',
    beforeSend: function (request) {
      request.setRequestHeader('Zotero-API-Key', api_key);
    },
    success: function (data, status, response) {
      data.forEach(function (tag_container) {
        global_dataset[global_hash[key]]['tags'].push(tag_container['tag']);
      });
      localStorage['dataset'] = JSON.stringify(global_dataset);
      show_list('');
    }
  });
}

// Renders

function show_error(msg) {
  $('tbody').empty();
  $('tbody').append('<tr><td>' + msg + '</td></tr>');
}

function show_list(req) {
  var options = {
    shouldSort: true,
    threshold: 0.4,
    location: 0,
    distance: 100,
    maxPatternLength: 32,
    minMatchCharLength: 1,
    keys: [
      'title',
      'url',
      'itemType',
      'date',
      'language',
      'tags',
      'tags',
      'creators.firstName',
      'presentationType'
    ]
  };

  var fuse = new Fuse(global_dataset, options);
  var result = req ? fuse.search(req) : global_dataset;
  $('tbody').empty();
  result.forEach(function (element) {
    var type = element['itemType'];
    $('tbody').append(
      type == 'blogPost' ? render_blogPost(element) :
      type == 'webpage' ? render_webpage(element) :
      type == 'presentation' ? render_presentation(element) :
      type == 'conferencePaper' ? render_conferencePaper(element) :
      type == 'journalArticle' ? render_journalArticle(element) :
      render_misc(element)
    );
  });
}

function render_tags(element) {
  return element['tags'].map(x => '<a href="#" class="tag">' + x + '</a>').join(' ');
}

function render_blogPost(element) {
  var data = [element['title'], render_tags(element)];
  return render_element(data);
}

function render_webpage(element) {
  var data = [element['title'], render_tags(element)];
  return render_element(data);
}

function render_presentation(element) {
  var data = [element['title'], render_tags(element)];
  return render_element(data);
}

function render_conferencePaper(element) {
  var data = [element['title'], render_tags(element)];
  return render_element(data);
}

function render_journalArticle(element) {
  var data = [element['title'], render_tags(element)];
  return render_element(data);
}

function render_misc(element) {
  var data = [element['title'], render_tags(element)];
  return render_element(data);
}

function render_element(data) {
  data.push("<i class='fa fa-qrcode' aria-hidden='true'></i>");
  return '<tr><td>' + data.join('</td><td>') + '</td></tr>'
}