var global_publications = new Array();
var global_hash = new Map();
var idx = undefined;

// Click control ----------------------------------------------------------

$(document).on('click', '.tag', function (e) {
  e.preventDefault();
  $('#request').val($(e.target).text());
  hide_all_publications();
  search_and_show_publications();
});

$('#request').on('keyup', function () {
  hide_qr_container();
  hide_message_container();
  hide_all_publications();
  show_publications_container();
  show_all_tbody();
  try {
    search_and_show_publications();
  } catch (e) {
    console.log(e);
    message("Search doesn't work");
  }
  hide_tbody_without_visible_publications();
});

document.addEventListener('keydown', function (event) {
  if (event.key === 'Escape') {
    hide_message_container();
    hide_qr_container();
    show_publications_container();
  }
});


$(document).on('click', '.qr', function (e) {
  e.preventDefault();
  const publication_id = e.target.closest('tr').id;
  if (!publication_id) {
    return;
  }

  hide_publications_container();
  show_qr_container();
  var domainName = window.location.href;
  var element = global_publications[global_hash[publication_id]];
  var link = domainName + '?d=' + element["id"];
  var el = kjua({ text: link, fill: '#111111', size: 400 });
  $('#qrcode a').html(el);
  $('#qrcaption').html(element["title"]);
  $('#qrlink a').attr('href', link).html(link);
});

$(document).on('click', '#qrcode', function (e) {
  e.preventDefault();
  hide_qr_container();
  show_publications_container();
});



// Data control -----------------------------------------------------------


function loadJSON(callback) {
  var xobj = new XMLHttpRequest();
  xobj.overrideMimeType("application/json");
  xobj.open('GET', 'publications.json', true);
  xobj.onreadystatechange = function () {
    if (xobj.readyState == 4 && xobj.status == "200") {
      callback(xobj.responseText);
    }
  };
  xobj.send(null);
}


function build_search_index(callback) {
  idx = lunr(function () {
    this.use(lunr.multiLanguage('en', 'ru'))
    this.ref('id');
    this.field('title');
    this.field('year');
    this.field('type');
    this.field('tags');
    this.field('authors');
    global_publications.forEach(function (element) {
      this.add(element);
    }, this);
  });

  if (callback) callback();
}


function fill_hashes(callback) {
  var i = 0;
  global_publications.forEach(function (element) {
    global_hash[element['id']] = i;
    i++;
  });

  if (callback) callback();
};

$(document).ready(function () {
  loadJSON(function (response) {
    global_publications = JSON.parse(response);
    build_search_index();
    fill_hashes(function () {
      process_url();
    });
  });
});


function message(msg) {
  hide_publications_container();
  hide_qr_container();
  $('#message').html(msg);
  show_message_container();
};


function search_and_show_publications() {
  const req = $('#request').val() ? $('#request').val() : '';
  if (req) {
    const result = idx.search(req);
    result.forEach(function (element) {
      show_item_by_id(element['ref'])
    });

  }
  else {
    show_all_publications();
  }
};

function process_url() {
  var searchParams = new URLSearchParams(window.location.search)
  if (searchParams.has('d')) {
    const req = searchParams.get('d').toLowerCase();
    redirect_to(req);
  }
  if (searchParams.has('q')) {
    search_query(searchParams.get('q'))
  }
};

function redirect_to(publication_id) {
  if (!(publication_id in global_hash)) {
    message('Hi! We didn\'t find publication "' + publication_id + '"');
  }

  const publication_idx = global_hash[publication_id];
  const publication = global_publications[publication_idx];

  if (!('url' in publication)) {
    message('Hi! There is no url in publication "' + publication_id + '"');
  }

  window.location.replace(publication['url']);
};

function search_query(query) {
  $('#request').val(query).trigger('keyup');
};


// Visual control ---------------------------------------------------------

function hide(element_id) {
  var element = document.getElementById(element_id);
  element.style.display = "none";
};

function show(element_id) {
  var element = document.getElementById(element_id);
  element.style.display = "";
};

function show_qr_container() {
  show("qrcontainer");
};

function hide_qr_container() {
  hide("qrcontainer");
};

function show_publications_container() {
  show("publicationscontainer");
};

function hide_publications_container() {
  hide("publicationscontainer");
};

function show_message_container() {
  show("messagecontainer");
};

function hide_message_container() {
  hide("messagecontainer");
};

function show_all_tbody() {
  var tbodyElements = document.querySelectorAll("tbody.group");
  for (var j = 0; j < tbodyElements.length; j++) {
    tbodyElements[j].style.display = "";
  }
}

function hide_tbody_without_visible_publications() {
  var tbodyElements = document.querySelectorAll("tbody.group");
  for (var j = 0; j < tbodyElements.length; j++) {
    var publications = tbodyElements[j].querySelectorAll(".publication");

    let all_publications_hidden = true;

    publications.forEach(row => {
      if (row.style.display !== "none") {
        all_publications_hidden = false;
      }
    });

    if (all_publications_hidden) {
      tbodyElements[j].style.display = "none";
    }
  }
};

function hide_all_publications() {
  var trElements = document.querySelectorAll("tr.publication");
  for (var j = 0; j < trElements.length; j++) {
    trElements[j].style.display = "none";
  }
};

function show_all_publications() {
  var trElements = document.querySelectorAll("tr.publication");
  for (var i = 0; i < trElements.length; i++) {
    trElements[i].style.display = "";
  }
};

function show_item_by_id(id_str) {
  var trElement = document.getElementById(id_str);
  if (trElement) {
    trElement.style.display = "";
  } else {
    console.log("Element with id '" + id_str + "' not found");
  }
};
