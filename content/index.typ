#import "../config.typ": template, tufted
#show: template.with(
  title: "Anatoly Tsyplenkov",
  description: "Personal website and blog of Anatoly Tsyplenkov, geomorphologist and software engineer.",
  page-type: "blog",
)

= Blog

Notes on R, sediments, geospatial work, and research software.

#tufted.blog-entry(
  date: datetime(year: 2022, month: 3, day: 5),
  path: "/blog/2022-03-05-soilgrids-terra/",
  title: "Accessing SoilGrids via {terra}",
)

#tufted.blog-entry(
  date: datetime(year: 2020, month: 3, day: 3),
  path: "/blog/2020-03-03-tidy-tuesday-nhl/",
  title: "Tidy Tuesday NHL",
)
