/**
 * shared/charts.js — Chart.js helpers & themed defaults
 *
 * Reads CSS variables from <html> so charts follow the active theme (dark/light).
 * Listens to the 'anef:theme-change' event dispatched by nav.js to recolor
 * existing chart instances on the fly.
 */
(function() {
  'use strict';

  window.ANEF = window.ANEF || {};

  var instances = {};

  /** Read a CSS custom property from the document root. */
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function themeColors() {
    return {
      text:       cssVar('--text')       || '#e2e8f0',
      textMuted:  cssVar('--text-muted') || '#94a3b8',
      border:     cssVar('--border')     || '#334155',
      bgCard:     cssVar('--bg-card')    || '#1e293b'
    };
  }

  /** Apply (or re-apply) themed Chart.defaults — call after any theme change. */
  function registerDarkTheme() {
    if (typeof Chart === 'undefined') return;
    var c = themeColors();

    Chart.defaults.color = c.textMuted;
    Chart.defaults.borderColor = c.bgCard;
    Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

    Chart.defaults.plugins.legend.labels.color = c.text;
    Chart.defaults.plugins.legend.labels.padding = 12;
    Chart.defaults.plugins.tooltip.backgroundColor = c.bgCard;
    Chart.defaults.plugins.tooltip.titleColor = c.text;
    Chart.defaults.plugins.tooltip.bodyColor = c.textMuted;
    Chart.defaults.plugins.tooltip.borderColor = c.border;
    Chart.defaults.plugins.tooltip.borderWidth = 1;

    Chart.defaults.scale.grid.color = c.bgCard;
    Chart.defaults.scale.ticks.color = c.textMuted;
  }

  /** Walk a chart's options and replace previously-themed colors with the
   *  current ones. Charts re-cache config at create-time, so we mutate
   *  their options object then call .update('none') for an instant repaint. */
  function recolorInstance(chart) {
    var c = themeColors();
    var opts = chart.options || {};

    if (opts.plugins) {
      if (opts.plugins.legend && opts.plugins.legend.labels) {
        opts.plugins.legend.labels.color = c.text;
      }
      if (opts.plugins.tooltip) {
        opts.plugins.tooltip.backgroundColor = c.bgCard;
        opts.plugins.tooltip.titleColor = c.text;
        opts.plugins.tooltip.bodyColor = c.textMuted;
        opts.plugins.tooltip.borderColor = c.border;
      }
      if (opts.plugins.datalabels && typeof opts.plugins.datalabels === 'object'
          && opts.plugins.datalabels.color) {
        opts.plugins.datalabels.color = c.text;
      }
    }
    if (opts.scales) {
      Object.keys(opts.scales).forEach(function(k) {
        var s = opts.scales[k];
        if (!s) return;
        if (s.ticks) s.ticks.color = c.textMuted;
        if (s.grid) s.grid.color = c.bgCard;
      });
    }
    chart.update('none');
  }

  // Recolor on theme change. Uses a microtask so the CSS variables on
  // <html> are guaranteed up-to-date before we read them.
  document.addEventListener('anef:theme-change', function() {
    setTimeout(function() {
      registerDarkTheme();
      Object.keys(instances).forEach(function(name) {
        try { recolorInstance(instances[name]); } catch (e) {}
      });
    }, 0);
  });

  /** Create (or replace) a named chart */
  function createChart(name, canvasId, config) {
    destroyChart(name);
    var canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    var chart = new Chart(canvas, config);
    instances[name] = chart;
    return chart;
  }

  /** Destroy a named chart */
  function destroyChart(name) {
    if (instances[name]) {
      instances[name].destroy();
      delete instances[name];
    }
  }

  /** Destroy all charts */
  function destroyAll() {
    var keys = Object.keys(instances);
    for (var i = 0; i < keys.length; i++) {
      instances[keys[i]].destroy();
    }
    instances = {};
  }

  /** Get a chart instance by name */
  function getChart(name) {
    return instances[name] || null;
  }

  /** Doughnut chart config helper */
  function doughnutConfig(labels, values, colors) {
    var c = themeColors();
    return {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: colors.map(function(col) { return col + 'cc'; }),
          borderColor: colors,
          borderWidth: 2,
          hoverOffset: 8
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: { color: c.text, font: { size: 11 }, padding: 12 }
          },
          tooltip: {
            callbacks: {
              label: function(ctx) {
                var total = ctx.dataset.data.reduce(function(a, b) { return a + b; }, 0);
                var pct = ((ctx.parsed / total) * 100).toFixed(0);
                return ' ' + ctx.label + ': ' + ctx.parsed + ' (' + pct + '%)';
              }
            }
          }
        }
      }
    };
  }

  /** Horizontal bar config helper */
  function horizontalBarConfig(labels, values, colors, opts) {
    opts = opts || {};
    var c = themeColors();
    return {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: opts.label || '',
          data: values,
          backgroundColor: typeof colors === 'string' ? colors : colors.map(function(col) { return col + '99'; }),
          borderColor: typeof colors === 'string' ? colors : colors,
          borderWidth: 1,
          borderRadius: 4
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          datalabels: opts.datalabels || false
        },
        scales: {
          x: {
            ticks: { color: c.textMuted, callback: function(v) { return v + (opts.suffix || ''); } },
            grid: { color: c.bgCard }
          },
          y: {
            ticks: { color: c.textMuted, font: { size: 11 } },
            grid: { display: false }
          }
        }
      }
    };
  }

  /** Line chart config helper */
  function lineConfig(labels, datasets, opts) {
    opts = opts || {};
    var c = themeColors();
    return {
      type: 'line',
      data: {
        labels: labels,
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { labels: { color: c.text } },
          datalabels: false
        },
        scales: {
          x: {
            ticks: { color: c.textMuted, font: { size: 10 }, maxRotation: 45 },
            grid: { color: c.bgCard }
          },
          y: {
            ticks: { color: c.textMuted, callback: function(v) { return v + (opts.ySuffix || ''); } },
            grid: { color: c.bgCard },
            beginAtZero: opts.beginAtZero !== false
          }
        }
      }
    };
  }

  /** Bar chart config helper */
  function barConfig(labels, datasets, opts) {
    opts = opts || {};
    var c = themeColors();
    var plugins = [];
    if (typeof ChartDataLabels !== 'undefined' && opts.datalabels !== false) plugins.push(ChartDataLabels);

    return {
      type: 'bar',
      plugins: plugins,
      data: {
        labels: labels,
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: c.text } },
          datalabels: opts.datalabels || {
            color: c.text,
            font: { size: 10, weight: 'bold' },
            anchor: 'end',
            align: 'top',
            formatter: function(v) { return v != null ? v + (opts.suffix || '') : ''; }
          },
          tooltip: {
            callbacks: {
              label: function(ctx) {
                return ctx.dataset.label + ': ' + ctx.parsed.y + (opts.suffix || '');
              }
            }
          }
        },
        scales: {
          x: {
            ticks: { color: c.textMuted, font: { size: 10 }, maxRotation: 45 },
            grid: { color: c.bgCard },
            stacked: opts.stacked || false
          },
          y: {
            ticks: { color: c.textMuted, callback: function(v) { return v + (opts.ySuffix || ''); } },
            grid: { color: c.bgCard },
            stacked: opts.stacked || false,
            beginAtZero: true
          }
        }
      }
    };
  }

  ANEF.charts = {
    registerDarkTheme: registerDarkTheme,
    create: createChart,
    destroy: destroyChart,
    destroyAll: destroyAll,
    get: getChart,
    doughnutConfig: doughnutConfig,
    horizontalBarConfig: horizontalBarConfig,
    lineConfig: lineConfig,
    barConfig: barConfig
  };
})();
