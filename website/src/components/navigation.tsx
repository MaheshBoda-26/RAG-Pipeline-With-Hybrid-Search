"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Sun, Moon, Github } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const navLinks = [
  { href: "#features", label: "Features" },
  { href: "#architecture", label: "Architecture" },
  { href: "#demo", label: "Live Demo" },
  { href: "#docs", label: "Docs" },
];

/* Anthropic-style radial-spike brand mark: a 4-spoke asterisk glyph. */
function SpikeMark({ className }: { className?: string }) {
  return (
    <svg
      className={cn("w-6 h-6", className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    >
      <path d="M12 3v18M4 6l16 12M20 6L4 18" />
      <path d="M12 3c-1.2 2-1.2 2 0 4M3.5 5.5c1.2 2 1.2 2 0 4M20.5 5.5c-1.2 2-1.2 2 0 4M13 12c-1-2-1-2 0-4" opacity="0" />
    </svg>
  );
}

export function Navigation() {
  const [isOpen, setIsOpen] = React.useState(false);
  const [isScrolled, setIsScrolled] = React.useState(false);
  const [isDark, setIsDark] = React.useState(false);

  React.useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  React.useEffect(() => {
    const saved = localStorage.getItem("theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initialDark = saved ? saved === "dark" : prefersDark;
    setIsDark(initialDark);
    document.documentElement.classList.toggle("dark", initialDark);
  }, []);

  const toggleTheme = () => {
    const newDark = !isDark;
    setIsDark(newDark);
    localStorage.setItem("theme", newDark ? "dark" : "light");
    document.documentElement.classList.toggle("dark", newDark);
  };

  return (
    <motion.nav
      initial={{ y: -100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        "fixed top-0 left-0 right-0 z-50 bg-canvas transition-all duration-300 ease-out",
        isScrolled && "border-b border-hairline backdrop-blur-md bg-canvas/90"
      )}
      role="navigation"
      aria-label="Main navigation"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <motion.a
            href="#"
            className="flex items-center gap-2 text-lg text-ink"
            aria-label="RAG Pipeline Home"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <SpikeMark />
            <span className="hidden sm:block font-medium tracking-tight">RAG Pipeline</span>
          </motion.a>

          <div className="hidden md:flex items-center gap-8">
            {navLinks.map((link, index) => (
              <motion.a
                key={link.href}
                href={link.href}
                className="text-sm font-medium text-muted-foreground hover:text-ink transition-colors duration-200 relative"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05, duration: 0.3 }}
              >
                {link.label}
                <motion.span
                  className="absolute bottom-[-4px] left-0 right-0 h-0.5 bg-coral origin-left scale-x-0"
                  initial={false}
                  whileHover={{ scaleX: 1 }}
                  transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
                />
              </motion.a>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
              className="text-muted-foreground hover:text-ink"
            >
              {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </Button>
            <motion.a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-ink transition-colors duration-200"
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              aria-label="View on GitHub"
            >
              <Github className="w-5 h-5" />
            </motion.a>
            <Button asChild className="bg-coral text-on-primary hover:bg-coral-active rounded-lg h-10 px-5">
              <a href="#demo">Try Pipeline</a>
            </Button>
          </div>

          <button
            className="md:hidden p-2 text-muted-foreground hover:text-ink"
            onClick={() => setIsOpen(!isOpen)}
            aria-expanded={isOpen}
            aria-controls="mobile-menu"
            aria-label="Toggle navigation"
          >
            {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            id="mobile-menu"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className={cn(
              "md:hidden overflow-hidden border-t border-hairline bg-canvas",
              isScrolled && "backdrop-blur-md"
            )}
          >
            <div className="px-4 py-4 space-y-4">
              {navLinks.map((link, index) => (
                <motion.a
                  key={link.href}
                  href={link.href}
                  className="block text-base font-medium text-muted-foreground hover:text-ink transition-colors"
                  onClick={() => setIsOpen(false)}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                >
                  {link.label}
                </motion.a>
              ))}
              <div className="flex items-center gap-4 pt-4 border-t border-hairline">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={toggleTheme}
                  aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
                >
                  {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                </Button>
                <motion.a
                  href="https://github.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-muted-foreground hover:text-ink"
                  whileHover={{ scale: 1.1 }}
                >
                  <Github className="w-5 h-5" />
                </motion.a>
                <Button asChild className="bg-coral text-on-primary hover:bg-coral-active rounded-lg h-10 px-5 ml-auto">
                  <a href="#demo">Try Pipeline</a>
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  );
}