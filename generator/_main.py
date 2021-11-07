import pdf2image
import requests
from pyzotero import zotero

library_id = 4809962
library_type = 'user'
api_key = 'hTvqMYvC4Bjhm4xGHqyCTSWv'

zot = zotero.Zotero(library_id, library_type, api_key)
items = zot.publications()

for item in items:
    key = item['data']['key']
    print('Item: %s | Key: %s' % (item['data']['itemType'], key))
    item_details = zot.item(key)
    print(item_details.keys())
    for k, v in item_details['data'].items():
        print(f'{k}: {v}')
    children_list = zot.children(key)
    for child in children_list:
        print(child['data'])
    url = item_details['data']['url']
    print(url)
    r = requests.get(url)

    images = pdf2image.convert_from_bytes(r.content, dpi=100)

    with open("CFXSID8E.html", 'w') as f:
        f.write("""
            <!doctype html>
            <html>
                <head>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">

                    <title>reveal.js</title>

                    <link rel="stylesheet" href="reveal.js-master/dist/reset.css">
                    <link rel="stylesheet" href="reveal.js-master/dist/reveal.css">
                    <link rel="stylesheet" href="reveal.js-master/dist/theme/black.css">

                    <!-- Theme used for syntax highlighted code -->
                    <link rel="stylesheet" href="reveal.js-master/plugin/highlight/monokai.css">
                </head>
                <body>
                <div class="reveal">
                        <div class="slides">
            """)
        f.write(f"""
                    <section>
                        <h3>{item_details['data']['title']}</h3>
                        <p>
                            <small>Created by <a href="http://hakim.se">Hakim El Hattab</a> and <a href="https://github.com/hakimel/reveal.js/graphs/contributors">contributors</a></small>
                        </p>
                        <p>
                            <small>{item_details['data']['date']}</small>
                        </p>
                    </section>
                """)
        for i in range(len(images)):
            images[i].save('page' + str(i) + '.png', 'PNG')
            f.write(f"""
                    <section>
                    <img class="r-stretch" src="{'page' + str(i) + '.png'}">
                    </section>
                """)
        f.write("""
                            </div>
                    </div>
                    <script src="reveal.js-master/dist/reveal.js"></script>
                    <script src="reveal.js-master/plugin/notes/notes.js"></script>
                    <script src="reveal.js-master/plugin/markdown/markdown.js"></script>
                    <script src="reveal.js-master/plugin/highlight/highlight.js"></script>
                    <script>
                        // More info about initialization & config:
                        // - https://revealjs.com/initialization/
                        // - https://revealjs.com/config/
                        Reveal.initialize({
                            hash: true,

                            // Learn about plugins: https://revealjs.com/plugins/
                            plugins: [ RevealMarkdown, RevealHighlight ]
                        });
                    </script>
                </body>
            </html>
            """)
    break
