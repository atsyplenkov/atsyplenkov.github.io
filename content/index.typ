#import "../config.typ": template, tufted
#show: template.with(
  title: "Anatoly Tsyplenkov",
  description: "Personal website and blog of Anatoly Tsyplenkov, geomorphologist and software engineer.",
  page-type: "blog",
)

= Blog

Notes on R, sediments, geospatial work, and research software.

#tufted.blog-entry(
  date: datetime(year: 2024, month: 8, day: 6),
  path: "/blog/2024-08-06-xgboost-gpu-r/",
  title: "Accelerating XGBoost with GPU in R",
)

#tufted.blog-entry(
  date: datetime(year: 2024, month: 2, day: 11),
  path: "/blog/2024-02-11-anzgg2024/",
  title: "Supplementary material to poster presentation @ ANZGG 2024",
)

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
