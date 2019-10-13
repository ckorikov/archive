const zotero = 'https://api.zotero.org/users/4809962/';
const api_key = 'hTvqMYvC4Bjhm4xGHqyCTSWv';
const params = '?sort=date&limit=100';

var global_hash = new Map();
var global_links_hash = new Map();
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
  show_list();
});

$(document).on('click', '.tag', function (e) {
  e.preventDefault();
  $('#request').val($(e.target).text() + ' ');
  show_list();
});

$(document).on('click', '.qr', function (e) {
  e.preventDefault();
  $('tbody').empty();
  var element = global_dataset[global_hash[e.target.id]];
  var link = 'https://korikov.cc/?d='+get_human_key(element);
  var el = kjua({
    text: link,
    fill: '#111111',
    size: 400
  });
  $('tbody').append('<tr><td id="qrcode"><a href="#"></a></td></tr>' +
                    '<tr><td id="qrcaption">' + element['title'] + '</td><tr>'+
                    '<tr><td id="qrlink"><a href="'+link+'">' + link + '</a></td><tr>');
  $('#qrcode a').append(el);
});

$(document).on('click', '#qrcode', function (e) {
  e.preventDefault();
  show_list();
});

// Loaders

function load_from_zotero() {
  $.ajax({
    url: zotero + 'publications/items' + params,
    crossDomain: true,
    dataType: 'json',
    beforeSend: function (request) {
      request.setRequestHeader('Zotero-API-Key', api_key);
    },
    success: function (data, status, response) {
      prepare_new_data(data, response.getResponseHeader('Last-Modified-Version'));
    },
    error: function (response) {
      show_error('No data');
    }
  });
}

function load_from_local_storage() {
  if (localStorage['dataset']) {
    global_dataset = JSON.parse(localStorage['dataset']);
    fill_hashes();
    process_user();
  } else {
    load_from_zotero();
  }
}

function process_user() {
  var searchParams = new URLSearchParams(window.location.search)
  if (searchParams.has('d')) {
    const req = searchParams.get('d').toLowerCase();
    if (req in global_links_hash && 'url' in global_dataset[global_links_hash[req]]) {
      window.location.replace(global_dataset[global_links_hash[req]]['url']);
    }
  }
  if (searchParams.has('q')) {
    $('#request').val(searchParams.get('q'));
  }
  show_list()
}

// Data processing

function fill_hashes() {
  var i = 0;
  global_dataset.forEach(function (element) {
    var key = get_human_key(element);
    global_links_hash[key] = i;
    global_hash[element['key']] = i;
    i++;
  });
}

function prepare_new_data(data, version) {
  data.sort(function (a, b) {
    var lexicographical_sort = function (a, b) {
      var a_data = a ? a.toLowerCase() : '';
      var b_data = b ? b.toLowerCase() : '';
      return ((a_data > b_data) ? -1 : ((a_data < b_data) ? 1 : 0));
    };
    return lexicographical_sort(a['data']['date'], b['data']['date']) ||
           lexicographical_sort(a['data']['title'], b['data']['title']);
  }).forEach(function (item) {
    var element = item['data'];
    if (element['itemType'] != 'attachment') {
      element['tags'] = new Array();
      const idx = global_dataset.push(element) - 1;
      global_links_hash[get_human_key(element)] = idx;
      global_hash[element['key']] = idx;
      process_tags(element['key']);
    }
  });
  localStorage['dataset'] = JSON.stringify(global_dataset);
  localStorage['version'] = version;
  process_user();
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
      process_user();
    }
  });
}

// Renders

function show_error(msg) {
  $('tbody').empty();
  $('tbody').append('<tr><td>' + msg + '</td></tr>');
}

function show_list() {
  const req = $('#request').val() ? $('#request').val() : '';
  const options = {
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
      'creators.firstName',
      'creators.lastName',
      'presentationType'
    ]
  };

  var fuse = new Fuse(global_dataset, options);
  const result = req ? fuse.search(req) : global_dataset;
  $('tbody').empty();
  result.forEach(function (element) {
    const type = element['itemType'];
    $('tbody').append(
      type == 'blogPost' ? render_blogPost(element) :
      type == 'webpage' ? render_webpage(element) :
      type == 'presentation' ? render_presentation(element) :
      type == 'conferencePaper' ? render_conferencePaper(element) :
      type == 'journalArticle' ? render_journalArticle(element) :
      type == 'magazineArticle' ? render_magazineArticle(element) :
      type == 'thesis' ? render_thesis(element) :
      type == 'videoRecording' ? render_video(element) :
      render_misc(element)
    );
  });
}

function render_tags(element) {
  return element['tags'].map(x => '<a href="#" class="tag">' + x + '</a>').join(' ');
}

function render_title(element) {
  if (element['url']) {
    return '<a href="' + element['url'] + '"  target="_blank">' + element['title'] + '</a>';
  } else {
    return '<stroke>' + element['title'] + '</stroke>';
  }
}

function render_qr(element) {
  return '<a href="#" class="qr"><i class="fa fa-qrcode" id="' + element['key'] + '"></i></a>';
}

function render_blogPost(element) {
  var meta = '<div class="meta"><span>' + get_year(element) + '</span></div>';
  var icon_type = element['websiteType'] == 'Habr' ? 'fas fa-heading' : 'fas fa-globe';
  var icon = '<span class="icon"><i class="' + icon_type + '"></i></span>';
  var data = [meta + icon + render_title(element), render_tags(element), render_qr(element)];
  return render_element(data);
}

function render_webpage(element) {
  var meta = '<div class="meta"><span>' + get_year(element) + '</span></div>';
  var icon_type = element['websiteType'] == 'GitHub' ? 'fab fa-github' : 'fas fa-globe';
  var icon = '<span class="icon"><i class="' + icon_type + '"></i></span>';
  var data = [meta + icon + render_title(element), render_tags(element), render_qr(element)];
  return render_element(data);
}

function render_presentation(element) {
  var meta = '<div class="meta"><span>' + get_year(element) + '</span></div>';
  var icon_type = element['presentationType'] == 'Lecture' ? 'fas fa-chalkboard-teacher' : 'fas fa-comments';
  var icon = '<span class="icon"><i class="' + icon_type + '"></i></span>';
  var data = [meta + icon + render_title(element), render_tags(element), render_qr(element)];
  return render_element(data);
}

function render_conferencePaper(element) {
  var meta = '<div class="meta"><span>' + get_year(element) + '</span></div>';
  var icon = '<span class="icon"><i class="fas fa-file-alt"></i></span>';
  var data = [meta + icon + render_title(element), render_tags(element), render_qr(element)];
  return render_element(data);
}

function render_journalArticle(element) {
  var meta = '<div class="meta"><span>' + get_year(element) + '</span></div>';
  var icon = '<span class="icon"><i class="fas fa-file-alt"></i></span>';
  var data = [meta + icon + render_title(element), render_tags(element), render_qr(element)];
  return render_element(data);
}

function render_magazineArticle(element) {
  var meta = '<div class="meta"><span>' + get_year(element) + '</span></div>';
  var icon = '<span class="icon"><i class="fas fa-book-open"></i></span>';
  var data = [meta + icon + render_title(element), render_tags(element), render_qr(element)];
  return render_element(data);
}

function render_thesis(element) {
  var meta = '<div class="meta"><span>' + get_year(element) + '</span></div>';
  var icon = '<span class="icon"><i class="fas fa-user-graduate"></i></span>';
  var data = [meta + icon + render_title(element), render_tags(element), render_qr(element)];
  return render_element(data);
}

function render_video(element) {
  var meta = '<div class="meta"><span>' + get_year(element) + '</span></div>';
  var icon = '<span class="icon"><i class="fas fa-video"></i></span>';
  var data = [meta + icon + render_title(element), render_tags(element), render_qr(element)];
  return render_element(data);
}

function render_misc(element) {
  var meta = '<div class="meta"><span>' + get_year(element) + '</span></div>';
  var icon = '<span class="icon"><i class="far fa-question-circle"></i></span>';
  var data = [meta + icon + render_title(element), render_tags(element), render_qr(element)];
  return render_element(data);
}

function render_element(data) {
  return '<tr><td>' + data.join('</td><td>') + '</td></tr>'
}

// Tools

function get_year(element) {
  return element['date'].split('/')[0];
}

function rus_to_latin(str) {
  var ru = {
      'а': 'a',
      'б': 'b',
      'в': 'v',
      'г': 'g',
      'д': 'd',
      'е': 'e',
      'ё': 'e',
      'ж': 'j',
      'з': 'z',
      'и': 'i',
      'к': 'k',
      'л': 'l',
      'м': 'm',
      'н': 'n',
      'о': 'o',
      'п': 'p',
      'р': 'r',
      'с': 's',
      'т': 't',
      'у': 'u',
      'ф': 'f',
      'х': 'h',
      'ц': 'c',
      'ч': 'ch',
      'ш': 'sh',
      'щ': 'shch',
      'ы': 'y',
      'э': 'e',
      'ю': 'u',
      'я': 'ya'
    },
    n_str = [];

  str = str.replace(/[ъь]+/g, '').replace(/й/g, 'i');

  for (var i = 0; i < str.length; ++i) {
    n_str.push(
      ru[str[i]] ||
      ru[str[i].toLowerCase()] == undefined && str[i] ||
      ru[str[i].toLowerCase()].replace(/^(.)/, function (match) {
        return match.toUpperCase()
      })
    );
  }
  return n_str.join('');
}

function get_human_key(element) {
  return get_year(element) + '-' + (rus_to_latin(element['title']).toLowerCase().replace(/[^a-zA-Z0-9 ]/g, '').replace(/\s+/g, '-'));
}