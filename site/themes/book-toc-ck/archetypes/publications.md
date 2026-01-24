---
title: "{{ replace .File.ContentBaseName "-" " " | title }}"
type: "publications"
items:
  - year: {{ now.Year }}
    items:
      - title: "Publication Title"
        authors: []
        tags: []
        pdf: false
        url: "#"
---
