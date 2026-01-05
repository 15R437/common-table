// static/js/tailwind-config.js
tailwind.config = {
  theme: {
    extend: {
      colors: {
        'page': 'var(--page-bg)',
        'nav': 'var(--nav-bg)',
        'brand': {
          dark: 'var(--dark)',
          light: 'var(--light)'
        },
      },
      fontFamily: {
        'sans': ['Inter','sans-serif'],
        'display': ['Oswald','sans-serif']
      },
      boxShadow: {
        'brand-glow': `0 10px 15px -3px rgba(var(--dark-rgba), 0.2), 0 4px 6px -2px rgba(var(--dark-rgba), 0.1)`,
        'brand-glow-hover': `0 20px 25px -5px rgba(var(--dark-rgba), 0.4), 0 4px 6px -2px rgba(var(--dark-rgba), 0.1)`
      }
    }
  }
}