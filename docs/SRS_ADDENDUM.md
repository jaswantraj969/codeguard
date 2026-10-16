# CodeGuard SRS Addendum — Version 1

| Item | Value |
|---|---|
| Amends | *CodeGuard — Mini Static Analyzer, SRS v1.0* (`docs/CodeGuard_SRS_15_Pages.docx`) |
| Addendum version | 1.0 |
| Date | 2026-10-16 |
| Status | Draft for supervisor approval |

## 1. Purpose and precedence

The SRS v1.0 describes CodeGuard well but leaves several things undefined. It never defines its C subset, and some of its rules are ambiguous. Two pairs of requirements duplicate each other, and some targets can't be verified within the project.

This addendum records the decisions made in the design review, along with the details settled during planning. **Where this addendum and the SRS disagree, this addendum wins.** Every change to an existing SRS requirement is listed in §12.

Keywords: **Must**, **Should**, **Could** and **Won't** keep the SRS meaning (§1.3).

## 2. Language subset (V1)

### 2.1 Supported

| Area | Supported in V1 |
|---|---|
| Types | `int`, `char`, `float`, `double`, `void`, each with an optional leading `const` |
| Declarations | Multiple declarators with optional initializers (`int a = 1, b;`), at file scope and block scope, and in the first clause of `for` |
| Functions | Definitions with parameters, prototypes (`int f(int);`), calls (including calls to functions defined later in the file), `return` with or without a value |
| Statements | Compound blocks, `if`/`else`, `while`, `for` (any clause may be empty), `break`, `continue`, `return`, expression statements, empty `;` |
| Expressions | See the precedence table in §3.3 |
| Address-of | `&identifier` only as a direct argument of a function call, e.g. `scanf("%d", &x)` |
| Literals | Integer (decimal, octal, hex), floating (with optional exponent and `f`/`F` suffix), character (with escapes), string (adjacent strings may be juxtaposed) |
| Comments | `// …` and `/* … */` (not nested) |

### 2.2 Preprocessor

CodeGuard does **not** run a preprocessor.

- Any line whose first non-blank character is `#` is skipped, together with any continuation lines that end in a backslash. A skipped line is not an error.
- An object-like `#define NAME value` registers `NAME` as a known constant symbol, visible from that line to the end of the file. The value is not expanded or folded.
- A function-like macro, `#define NAME(args) …`, is ignored and its name is not registered.
- `#include` files are not read. Library names come from the built-in list in §2.3.
- Conditional compilation (`#if`, `#ifdef`, `#else`, `#endif`) is skipped like any other `#` line. So code in **every** branch of an `#ifdef` is analyzed (see §11).

### 2.3 Known library names

One data file, `backend/data/known_library_functions.json`, lists library names that always count as declared. They are never reported by SEM-UNDECL and never appear in the symbol-table view.

- **Functions:**
  - `<stdio.h>`: `printf`, `scanf`, `puts`, `putchar`, `getchar`, `fprintf`, `fputs`, `fputc`, `fgetc`, `putc`, `getc`, `fflush`
  - `<stdlib.h>`: `abs`, `labs`, `exit`, `rand`, `srand`, `atoi`, `atof`, `malloc`, `free`
  - `<math.h>`: `sqrt`, `pow`, `fabs`, `ceil`, `floor`, `round`, `fmod`, `sin`, `cos`, `tan`, `exp`, `log`, `log10`
  - `<string.h>`: `strlen`, `strcmp`, `strncmp`, `strcpy`, `strncpy`, `strcat`, `memset`, `memcpy`
  - `<ctype.h>`: `isdigit`, `isalpha`, `isalnum`, `isspace`, `isupper`, `islower`, `toupper`, `tolower`
  - `<time.h>`: `time`
- **Constants:** `EOF`, `NULL`, `stdin`, `stdout`, `stderr`, `RAND_MAX`, `EXIT_SUCCESS`, `EXIT_FAILURE`, `INT_MAX`, `INT_MIN`, `CHAR_MAX`, `CHAR_MIN`

Library signatures are not checked, and library constants are never folded.

### 2.4 Unsupported in V1

Each of these produces an `UNSUPPORTED_CONSTRUCT` error with a specific message. None of them produces a generic syntax error.

| Construct | Trigger | Message |
|---|---|---|
| Arrays | `[` or `]` | Arrays are not supported in CodeGuard V1. |
| Pointers | `*` in a declarator, unary `*`, `->`, `&` anywhere except §2.1 | Pointers are not supported in CodeGuard V1. |
| struct / union / enum | keyword, or `.` member access | Structs, unions and enums are not supported in CodeGuard V1. |
| typedef | keyword | typedef is not supported in CodeGuard V1. |
| switch | `switch`, `case`, `default` | switch statements are not supported in CodeGuard V1; use if/else. |
| do/while | `do` | do/while loops are not supported in CodeGuard V1; use while. |
| goto / labels | `goto` | goto is not supported in CodeGuard V1. |
| Ternary | `?` or `:` | The ?: operator is not supported in CodeGuard V1; use if/else. |
| Casts | `(` type `)` before an expression | Casts are not supported in CodeGuard V1. |
| sizeof | keyword | sizeof is not supported in CodeGuard V1. |
| Extra type words | `unsigned`, `signed`, `long`, `short`, integer suffixes `u`/`l` | Only int, char, float, double and void are supported in CodeGuard V1. |
| Storage classes and qualifiers | `static`, `extern`, `register`, `auto`, `volatile`, `inline`, `restrict` | Storage classes and qualifiers other than const are not supported in CodeGuard V1. |
| Bitwise operators | `|`, `^`, `~`, `<<`, `>>`, their compound forms, `&` outside §2.1 | Bitwise operators are not supported in CodeGuard V1. |
| Comma operator | `,` outside a declarator list, parameter list or argument list | The comma operator is not supported in CodeGuard V1. |
| Unknown type names | `IDENT IDENT` at the start of a declaration (e.g. `bool b;`, `size_t n;`) | Unknown type name 'X': only int, char, float, double and void are supported (bool, size_t, FILE and typedef names are not). |
| Other keywords | `_Bool`, `_Complex`, `_Static_assert`, and similar | 'X' is not supported in CodeGuard V1. |

## 3. Grammar

### 3.1 Notation

ISO 14977-style EBNF:
- `=` defines a rule and `;` ends it.
- `|` separates alternatives.
- `[ … ]` is optional and `{ … }` repeats zero or more times.
- Terminals are quoted.

The grammar describes only the supported subset. The constructs in §2.4 are recognised and reported but not described here.

### 3.2 Syntactic grammar

```ebnf
translation_unit    = { external_decl } ;
external_decl       = function_def | function_proto | declaration ;

(* --- declarations --- *)
decl_specifiers     = [ "const" ] type_spec ;
type_spec           = "int" | "char" | "float" | "double" | "void" ;

function_def        = decl_specifiers identifier "(" param_list ")" compound_stmt ;
function_proto      = decl_specifiers identifier "(" proto_param_list ")" ";" ;
param_list          = "void" | [ param { "," param } ] ;
param               = decl_specifiers identifier ;
proto_param_list    = "void" | [ proto_param { "," proto_param } ] ;
proto_param         = decl_specifiers [ identifier ] ;

declaration         = decl_list ";" ;
decl_list           = decl_specifiers init_declarator { "," init_declarator } ;
init_declarator     = identifier [ "=" assignment_expr ] ;

(* --- statements --- *)
compound_stmt       = "{" { block_item } "}" ;
block_item          = declaration | statement ;
statement           = compound_stmt
                    | if_stmt
                    | while_stmt
                    | for_stmt
                    | jump_stmt
                    | expr_stmt ;
if_stmt             = "if" "(" expression ")" statement [ "else" statement ] ;
while_stmt          = "while" "(" expression ")" statement ;
for_stmt            = "for" "(" [ for_init ] ";" [ expression ] ";" [ expression ] ")" statement ;
for_init            = decl_list | expression ;
jump_stmt           = "break" ";" | "continue" ";" | "return" [ expression ] ";" ;
expr_stmt           = [ expression ] ";" ;

(* --- expressions (lowest to highest precedence) --- *)
expression          = assignment_expr ;
assignment_expr     = logical_or_expr
                    | identifier assign_op assignment_expr ;
assign_op           = "=" | "+=" | "-=" | "*=" | "/=" | "%=" ;
logical_or_expr     = logical_and_expr { "||" logical_and_expr } ;
logical_and_expr    = equality_expr { "&&" equality_expr } ;
equality_expr       = relational_expr { ( "==" | "!=" ) relational_expr } ;
relational_expr     = additive_expr { ( "<" | ">" | "<=" | ">=" ) additive_expr } ;
additive_expr       = multiplicative_expr { ( "+" | "-" ) multiplicative_expr } ;
multiplicative_expr = unary_expr { ( "*" | "/" | "%" ) unary_expr } ;
unary_expr          = ( "-" | "+" | "!" ) unary_expr
                    | ( "++" | "--" ) identifier
                    | postfix_expr ;
postfix_expr        = identifier ( "++" | "--" )
                    | primary_expr ;
primary_expr        = identifier "(" [ argument_list ] ")"
                    | identifier
                    | constant
                    | string_literal { string_literal }
                    | "(" expression ")" ;
argument_list       = argument { "," argument } ;
argument            = assignment_expr | "&" identifier ;
constant            = integer_literal | floating_literal | char_literal ;
```

Notes on the grammar:
- **Dangling else:** `else` binds to the nearest unmatched `if`.
- **Function placement:** function definitions and prototypes are allowed only at file scope.
- **Disambiguation:** after `decl_specifiers identifier`, a `(` selects a function. A `{` after the parameter list selects a definition, and a `;` selects a prototype.
- **Assignment target:** the left side of an assignment, and the operand of `++`/`--`, must be a plain identifier. Anything else gives `SYN-MALFORMED-EXPR`.
- **Jump placement:** the grammar accepts `break` and `continue` anywhere a statement can appear. Using them outside a loop breaks a semantic constraint, not the grammar, and is reported by `SEM-BREAK-CONTEXT` (§5.3).

### 3.3 Operator precedence (highest first)

| Level | Operators | Associativity |
|---|---|---|
| 1 | call `f(…)`, postfix `++` `--`, `( )` | left |
| 2 | unary `-` `+` `!`, prefix `++` `--` | right |
| 3 | `*` `/` `%` | left |
| 4 | `+` `-` | left |
| 5 | `<` `>` `<=` `>=` | left |
| 6 | `==` `!=` | left |
| 7 | `&&` | left |
| 8 | `\|\|` | left |
| 9 | `=` `+=` `-=` `*=` `/=` `%=` | right |

### 3.4 Lexical grammar

```ebnf
identifier        = ( letter | "_" ) { letter | digit | "_" } ;   (* ASCII only *)
integer_literal   = decimal_literal | octal_literal | hex_literal ;
decimal_literal   = nonzero_digit { digit } ;
octal_literal     = "0" { octal_digit } ;
hex_literal       = "0" ( "x" | "X" ) hex_digit { hex_digit } ;
floating_literal  = ( digits "." [ digits ] [ exponent ]
                    | "." digits [ exponent ]
                    | digits exponent ) [ "f" | "F" ] ;
exponent          = ( "e" | "E" ) [ "+" | "-" ] digits ;
digits            = digit { digit } ;
char_literal      = "'" ( c_char | escape ) "'" ;
string_literal    = '"' { s_char | escape } '"' ;
escape            = "\" ( "n" | "t" | "r" | "0" | "a" | "b" | "f" | "v"
                        | "\" | "'" | '"' | "?" )
                  | "\" octal_digit [ octal_digit [ octal_digit ] ]
                  | "\x" hex_digit { hex_digit } ;
(* c_char: any character except ', \ and newline;
   s_char: any character except ", \ and newline *)
line_comment      = "//" { any character except newline } ;
block_comment     = "/*" { any character } "*/" ;   (* not nested *)
```

Lexical details:
- **Keywords.** Supported: `int char float double void const if else while for break continue return`. All other C keywords are reserved: the lexer emits them as keyword tokens and the parser reports §2.4.
- **Unsupported punctuation.** `[ ] . -> ? : & | ^ ~ << >>` and their compound-assignment forms are lexed as valid tokens so the parser can report `UNSUPPORTED_CONSTRUCT`.
- **Line endings.** Before lexing, `\r\n` and `\r` are normalised to `\n`, and a leading UTF-8 BOM is dropped.
- **Positions.** Lines and columns are 1-based. Columns count Unicode code points, and a tab counts as one column.
- **Non-ASCII.** Any non-ASCII character outside a string, character literal or comment is `LEX-INVALID-CHAR`.

## 4. Pipeline

```
input validation → lexer → parser → symbol table + semantic rules → optimizer → report
```

1. **Input validation** happens in the API layer (§8). Failures are HTTP errors, not diagnostics.
2. **Lexer.** The lexer scans the whole source and reports every lexical error, up to 20. After an error it skips the bad character, string, literal or comment and continues. **If there is any lexical error, the pipeline stops after the lexer.**
3. **Parser.** Recursive descent with **panic-mode recovery**. When it finds an error, the parser:
   1. reports it,
   2. skips tokens until it reaches a `;` (which it consumes) or a `}` (which it leaves for the enclosing block), or the end of input,
   3. continues parsing from there.

   It never reports a second error at the same token position. After 20 syntax-stage errors it stops, and the stage detail says "Stopped after 20 syntax errors." Syntax-stage errors are `SYN-*`, `UNSUPPORTED_CONSTRUCT` and `NESTING_TOO_DEEP`. `NESTING_TOO_DEEP` ends parsing immediately. **If there is any syntax-stage error, the semantic and optimizer stages are skipped.**
4. **Semantic stage** builds the symbol table and runs the SEM-* rules (§5).
5. **Optimizer stage** runs OPT-CONSTEXPR. It reads SEM-CONSTCOND's results and never reports a condition that rule already reported.
6. **Report** merges the diagnostics, applies the one-diagnostic-per-construct policy (§5.1), sorts by line, column and severity (error, then warning, then suggestion), and computes statistics.

**Stage status.** Each of `lexical`, `syntax`, `semantic` and `optimizer` reports one of:
- `passed`: the stage ran and produced no error-severity diagnostics.
- `failed`: the stage ran and produced at least one error.
- `skipped`: the stage did not run.

The optimizer can't fail, because it only emits suggestions. The UI shows syntax-stage errors separately from later warnings.

### 4.1 Recursion safety

Analysis must never raise a Python `RecursionError`. Raising `sys.setrecursionlimit` is **not** an accepted fix. Instead:

- **Binary operators** are parsed by **precedence climbing**: one function handles all binary levels of §3.3, driven by a precedence table. A parenthesised subexpression therefore costs a few stack frames, not one per precedence level.
- **Chains are parsed iteratively, with loops instead of recursion:**
  - `else if` chains
  - unary prefix chains (`- - ! x`)
  - right-associative assignment chains (`a = b = c`): the operands are collected in a loop, then the tree is built right to left
- **Every pass over the AST is iterative** (explicit work stack) **or provably depth-bounded.** That includes the semantic visitors, the constant folder, the optimizer and the AST serializer. Recursion is allowed only where depth is bounded by the §7 limits, and the worst-case test (TC-38) proves it.
- The only recursion that remains in the parser is nested blocks, braceless statement bodies and parentheses, which are bounded by the nesting limits in §7.

**Missing semicolon position.** A missing `;` is reported at the end of the token before it, so the line number is the line where the `;` belongs, not the line of the next token.

## 5. Rules

### 5.1 Diagnostic format and policy

| Field | Type | Notes |
|---|---|---|
| `rule_id` | string | e.g. `SEM-UNUSED` |
| `severity` | `"error"` \| `"warning"` \| `"suggestion"` | |
| `message` | string | One line, names the identifier or value involved |
| `line`, `column` | int | 1-based start position |
| `end_line`, `end_column` | int \| null | End position, exclusive (one past the last character) |
| `explanation` | string | **Required.** One or two plain sentences for a student |
| `fix_hint` | string \| null | Optional concrete suggestion |

**One diagnostic per construct.** A construct (a declaration, an expression or a statement) gets at most one diagnostic. When several rules would report the same declaration, the first one in this order wins:

> SEM-DUP › SEM-SHADOW › SEM-UNUSED

The policy is applied after rule toggles. For example, if SEM-SHADOW is disabled, an unused shadowing variable reports SEM-UNUSED. The pairs that could overlap are separated by the definitions below:
- `if (0)`: only SEM-CONSTCOND.
- A constant condition: only SEM-CONSTCOND, never OPT-CONSTEXPR.
- `10 / 0`: only SEM-DIV0, never OPT-CONSTEXPR.

### 5.2 Constant folding (shared by SEM-DIV0, SEM-CONSTCOND and OPT-CONSTEXPR)

The module `semantic/folding.py` evaluates an expression at analysis time when every operand is constant:
- **Constant operands:** integer, floating and character literals, and `const`-qualified variables (global or local) whose initializer is itself constant. Library constants, `#define` names, parameters and non-`const` variables are never constant.
- **Types:** if every operand is an integer or character, the expression is `int`. If any operand is floating, it is `double`. Character literals fold to their character code.
- **Integer semantics follow C:**
  - `/` truncates toward zero.
  - `%` takes the sign of the dividend.
  - Comparisons, `!`, `&&` and `||` yield 0 or 1.
- **Overflow:** if an `int` result falls outside the 32-bit range −2,147,483,648 to 2,147,483,647, the expression is treated as not constant.
- **Short-circuit:** `&&` and `||` short-circuit. `0 && e` folds to 0 and `1 || e` folds to 1, even when `e` isn't constant.
- **Division by zero:** a division or remainder by zero stops folding (the result is not constant), and SEM-DIV0 reports it.
- **Not folded:** assignments, `++`/`--`, and calls.

### 5.3 Rule catalogue

All SEM-\* and OPT-\* rules are on by default. Each can be turned off through the API's `rules` field. Each rule is one module under `semantic/rules/` or `optimizer/`, with at least one positive and one negative unit test.

#### SEM-DUP — duplicate declaration (error)
- **Fires:** a name is declared twice in the **same scope**.
  - Parameters belong to the function's outermost block scope, so `int f(int a) { int a; }` fires.
  - At file scope, a variable and a function with the same name also fire.
  - Two definitions of the same function also fire.
- **Does not fire:**
  - The same name in different scopes (that's SEM-SHADOW).
  - A prototype followed by the definition, or repeated prototypes.
  - A repeated `#define`.
- **Reports** the second declaration. The first declaration stays in effect.
- **Example:** `int x; int x;` → "'x' is already declared in this scope (line 1)."
- **Explanation:** "Each name can be declared only once in the same scope. Rename one of them or remove the second declaration."

#### SEM-UNDECL — undeclared name (error)
- **Fires:** a name is used with no declaration visible at that point in the current or any enclosing scope.
  - **Variables:** a variable is visible from its declarator onward, so a use before the declaration fires.
  - **Functions** resolve file-wide, so a call to a function defined later doesn't fire.
  - **Library names (§2.3) and `#define` names** count as declared. A `#define` is visible from its line onward.
- **Reports** the first use of each undeclared name once per function, or once in total at file scope.
- **Example:** `y = 5;` with no `y` → "'y' is used but never declared."
- **Explanation:** "C requires every variable to be declared before it is used. Declare it with a type, for example `int y;`, before this line."

#### SEM-UNUSED — unused local variable (warning)
- **Fires:** a local variable (block scope or `for`-init) whose value is never **read**.
- **Not reads:**
  - The variable's initializer.
  - The left side of `=`.
  - A standalone statement whose only effect is to change the variable, such as `x++;`, `++x;`, `x += 1;` or the same in a `for` update clause.
  - `&x` passed to a call, which counts as a write.
- **Reads:** every other appearance. That includes a compound assignment or increment whose value is used, as in `y = x++;`.
- **Excluded:** parameters and global variables.
- **Reports** at the declaration.
- **Example:** `int unused = 50;` → "Variable 'unused' is declared but its value is never read."
- **Explanation:** "A variable whose value is never read has no effect on the program. Remove it, or use it where you meant to."

#### SEM-DIV0 — division by zero (error)
- **Fires:** the right operand of `/`, `%`, `/=` or `%=` is a literal zero (`0`, `0.0`, `'\0'`), or an expression that folds to zero under §5.2.
- **Never fires:** on a plain variable, even one assigned 0. `x / y` does not fire. `const int z = 0; x / z` and `x % 0` do.
- **Example:** `10 / 0` → "Division by zero."
- **Explanation:** "Dividing by zero is undefined in C and usually crashes the program. Check the divisor before dividing."

#### SEM-UNREACH — unreachable code (warning)
- **Fires:** a statement follows a `return`, `break` or `continue` in the **same block**.
- **Reports** once per block, at the first unreachable statement. The range extends to the last statement of the block.
- **Ignored:**
  - Empty statements (`;`).
  - `if (0)`, which belongs to SEM-CONSTCOND.
  - Code after an `if`/`else` that returns in both branches, since there's no flow analysis in V1.
- **Example:** `return 0; x = 1;` → "This code can never run."
- **Explanation:** "Statements after a return, break or continue in the same block are never executed. Remove them or move them before the jump."

#### SEM-CONSTCOND — constant condition (warning)
This is one merged rule that replaces SRS FR-SEM-07, FR-OPT-02 and FR-OPT-03. The semantic module owns it, and the optimizer only reads its results.
- **Fires:** the condition of an `if`, `while` or `for` folds to a constant under §5.2.
- **Exempt:**
  - `while (1)`, including redundant parentheses like `while ((1))`.
  - `for (;;)`.
  - Constants that come from `#define` or library names, since those aren't folded.
  - `for (;1;)` is **not** exempt. It is reported with a hint to write `for (;;)`.
- **Messages:**
  - `if` always false: "The condition is always false, so this branch never runs." This is the only diagnostic for `if (0)`.
  - `if` always true with an `else`: "The condition is always true, so the else branch never runs."
  - `if` always true without an `else`: "The condition is always true, so the if is unnecessary."
  - Loop always false: "The condition is always false, so the loop body never runs."
  - Loop always true: "The condition is always true, so this loop never ends unless it breaks." The hint is `while (1)` or `for (;;)`.
- **Example:** `if (10 > 5)` → the always-true message.
- **Explanation:** "A condition that does not depend on any variable always has the same result. It is usually a typo or leftover test code."

#### SEM-BREAK-CONTEXT — jump outside a loop (error)
This is a semantic **constraint check**, not a syntax error. The code matches the grammar, but C forbids it.
- **Fires:** a `break` or `continue` that is not inside a `while` or `for` body.
  - It is detected by the semantic pass, which tracks loop depth. The parser may record loop depth to help, but it never reports this as a syntax error, and the syntax stage still passes.
  - It is always on and cannot be turned off through `rules`, like the structural checks.
- **Does not fire:** a `break` or `continue` anywhere inside a loop body, including inside nested `if` blocks.
- **Example:** `void f(void) { break; }` → "'break' can only be used inside a loop."
- **Explanation:** "break leaves the nearest loop and continue jumps to its next iteration, so both need an enclosing while or for loop. switch is not supported in CodeGuard V1."

#### SEM-SHADOW — shadowing (warning)
- **Fires:** a variable or parameter declaration hides a user-declared variable, parameter or function in an enclosing scope. Library names and `#define` names are not considered.
- **Example:** a global `int x;` and a local `int x;` → "'x' hides the declaration on line 1."
- **Explanation:** "Inside this scope, the name refers to the new variable, not the outer one. This is legal but often a mistake; consider a different name."

#### OPT-CONSTEXPR — constant expression (suggestion)
- **Fires:** a **maximal** arithmetic subexpression (`+ - * / %`, unary `-` `+`, parentheses) whose operands are all integer or floating **literals**, and which isn't already a single literal. A unary `-` or `+` directly on a literal counts as a single literal, and so does `(5)`. "Maximal" means `1 + 2 + 3` gives one suggestion, not two.
- **Never fires:**
  - Inside a condition already reported by SEM-CONSTCOND.
  - On an expression containing a division by zero, or one whose folding overflows.
  - On character or string literals, or on `const` variables.
- **Example:** `10 + 20` → "'10 + 20' can be written as 30." The fix hint is "Replace with 30." For `7 / 2` the explanation adds that integer division truncates, so the result is 3.
- **Explanation:** "This calculation uses only fixed numbers, so its result is always the same. Writing the result directly can make the code clearer; the compiler does this for you anyway."
- **Never** rewrites the user's source (FR-OPT-06).

### 5.4 Structural diagnostics (all errors, not toggleable)

| Rule ID | Stage | Condition |
|---|---|---|
| `LEX-INVALID-CHAR` | lexical | Character not allowed in C source (e.g. `@`, `$`, `` ` ``, non-ASCII outside strings and comments) |
| `LEX-UNTERMINATED-STRING` | lexical | String reaches a newline or end of file before its closing `"` |
| `LEX-UNTERMINATED-CHAR` | lexical | Character literal reaches a newline or end of file before its closing `'` |
| `LEX-UNTERMINATED-COMMENT` | lexical | `/*` without a matching `*/` |
| `LEX-BAD-CHAR-LITERAL` | lexical | Empty `''` or more than one character |
| `LEX-BAD-ESCAPE` | lexical | Unknown escape such as `\q` |
| `LEX-BAD-NUMBER` | lexical | Malformed number, e.g. `08`, `0x`, `1e`, `123abc` |
| `SYN-MISSING-SEMICOLON` | syntax | Expected `;` |
| `SYN-UNMATCHED-BRACE` | syntax | `{` never closed (reported at the `{`), or `}` with no matching `{` |
| `SYN-UNMATCHED-PAREN` | syntax | `(` never closed, or `)` with no matching `(` |
| `SYN-MALFORMED-EXPR` | syntax | Missing operand, invalid assignment target, and similar |
| `SYN-UNEXPECTED-TOKEN` | syntax | Any other token that doesn't fit the grammar |
| `UNSUPPORTED_CONSTRUCT` | syntax | Any construct in §2.4 |
| `NESTING_TOO_DEEP` | syntax | Limit in §7 exceeded |

## 6. Symbol table

- **Scope tree:** `file` → `function` (parameters and the outermost body block share this scope) → `block`. A `for` statement with a declaration in its first clause opens a `for` scope, and its body block nests inside that.
- **Each symbol records:** name, kind (`variable`, `parameter`, `function`, `define`), type as text (e.g. `const int`, or `int (int, float)` for functions), declaration line and column, read count and write count. For functions, the read count is the number of calls.
- The built-in library scope sits above the file scope and is not returned to the client.

## 7. Limits and robustness

| Limit | Value | Behaviour |
|---|---|---|
| Source size | ≤ 512,000 bytes of the `source` field encoded as UTF-8 (not counting the JSON envelope) | The frontend checks it first, and the API enforces it with 413 `INPUT_TOO_LARGE`. Exactly 512,000 bytes is accepted. |
| Request body | ≤ 3,200,000 bytes | Rejected with 413 before JSON parsing. This cap is high enough that a valid 512,000-byte source can never hit it, even when every character is JSON-escaped. |
| Statement nesting | Depth ≤ 64. Each `{ }` block counts as one level, and so does each braceless `if`/`else`/`while`/`for` body. An `else if` link does **not** add a level. | 65 levels give `NESTING_TOO_DEEP` |
| Parenthesis nesting | Depth ≤ 64 within one expression. Grouping and call parentheses both count, and this is counted separately from statement nesting. | 65 levels give `NESTING_TOO_DEEP` |
| Chains | `else if` chains, unary prefix chains and chained assignments: ≤ 256 links each. They are parsed iteratively (§4.1). | 257 links give `NESTING_TOO_DEEP` |
| Worst case | 64 nested blocks around 64 nested parentheses, a 256-link `else if` chain and a 256-deep unary chain | Must complete in the real worker process with no `RecursionError` (TC-38) |
| Errors per stage | 20 lexical, 20 syntax | Later errors are dropped, and the stage detail notes it |
| Timeout | 5 s per analysis (`ANALYSIS_TIMEOUT_SECONDS`) | Analyses run in a small **pool of long-lived worker processes** (the `pebble` library), not a fresh process per request. The pool size equals the concurrency limit. A worker that times out is killed and replaced. A CPU-bound thread can't be killed, so a thread pool isn't enough. The response is 503 `ANALYSIS_TIMEOUT`. |
| Concurrency | 2 simultaneous analyses (`MAX_CONCURRENT_ANALYSES`), limited by a semaphore. The default matches the 512 MB free host. | A request waits up to 3 s (`QUEUE_WAIT_SECONDS`) for a free slot, then gets 503 `SERVICE_UNAVAILABLE` with `Retry-After`. |
| Rate limit | 30 analyses per minute per IP (`RATE_LIMIT_PER_MINUTE`); `/health` is exempt | 429 `RATE_LIMITED` with `Retry-After`. The client IP comes from `X-Forwarded-For` only when `TRUST_PROXY_HEADERS=true`. |
| Teaching views | Up to 10,000 tokens and 20,000 AST nodes are returned | The caps apply **only** to the `tokens` and `ast` fields. Analysis, diagnostics and `statistics` always cover the full input. Beyond the caps, `truncated.tokens` and `truncated.ast` are true, the token list is cut off and `ast` is `null`. |

- **Failures:** a malformed request never crashes the service. Stack traces are never returned. The client gets a safe error with the `analysis_id`, and the details are logged server-side under that ID.
- **Logging:** full source code is never logged, only its byte length and SHA-256 hash.
- **Execution:** submitted code is **never** executed, compiled or passed to any compiler or external tool. It is treated only as data.
- **Statelessness:** V1 is stateless. Nothing is stored, and `analysis_id` is a per-request trace UUID.

## 8. API

FastAPI, Python 3.12+, Pydantic v2. All bodies are JSON.

### 8.1 `GET /api/v1/health`

Response 200: `{"status": "ok"}`. The frontend calls this on load to wake the server.

### 8.2 `POST /api/v1/analyze`

**Request**

```json
{ "language": "c", "source": "int main(void) { return 0; }", "rules": { "SEM-SHADOW": false } }
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `language` | string | yes | Must be exactly `"c"` |
| `source` | string | yes | ≤ 512,000 UTF-8 bytes, not empty or whitespace-only |
| `rules` | object of rule ID → boolean | no | Only SEM-\* and OPT-\* IDs, except SEM-BREAK-CONTEXT. An unknown, structural or always-on ID gives 400. Rules that are left out stay on. |

Unknown extra top-level fields are ignored.

**Response 200.** This includes analyses that find errors in the code. Problems in the submitted code never produce an HTTP error.

```json
{
  "analysis_id": "6f1c…-uuid",
  "status": [
    { "stage": "lexical",   "status": "passed",  "detail": null },
    { "stage": "syntax",    "status": "passed",  "detail": null },
    { "stage": "semantic",  "status": "passed",  "detail": null },
    { "stage": "optimizer", "status": "passed",  "detail": null }
  ],
  "diagnostics": [
    { "rule_id": "SEM-UNUSED", "severity": "warning",
      "message": "Variable 'unused' is declared but its value is never read.",
      "line": 3, "column": 9, "end_line": 3, "end_column": 15,
      "explanation": "…", "fix_hint": null }
  ],
  "statistics": { "variables": 2, "functions": 1, "errors": 0, "warnings": 2,
                  "suggestions": 0, "tokens": 31, "lines": 8, "duration_ms": 4.2 },
  "tokens": [ { "type": "KEYWORD", "lexeme": "int", "line": 1, "column": 1 } ],
  "ast": { "type": "TranslationUnit", "label": "TranslationUnit",
           "line": 1, "column": 1, "end_line": 8, "end_column": 2,
           "children": [ … ] },
  "symbols": { "id": 0, "kind": "file", "name": null, "line": 1,
               "symbols": [ { "name": "main", "kind": "function", "type": "int (void)",
                              "line": 1, "column": 5, "reads": 0, "writes": 0 } ],
               "children": [ … ] },
  "truncated": { "tokens": false, "ast": false }
}
```

- `status` is always the four stages in this order. `detail` is a short note or `null`.
- `statistics`:
  - `variables` counts declared variables (globals and locals, not parameters).
  - `functions` counts distinct user-declared functions.
  - `errors`, `warnings` and `suggestions` are counted after the policy in §5.1.
  - `lines` is the number of source lines.
  - `duration_ms` is the analysis time in the worker, excluding any queue wait.
  - All counts cover the **full input**. `tokens` counts every token, even when the `tokens` view is truncated.
- `tokens` are returned even when lexing fails (the tokens scanned so far).
- `ast` is `null` unless the syntax stage passed.
- `symbols` is `null` unless the semantic stage ran.
- AST node `label` is human-readable (e.g. `BinaryOp +`, `Identifier x`, `IntLiteral 10`).

### 8.3 Error envelope

```json
{ "error": { "code": "INPUT_TOO_LARGE", "message": "Source is 600,000 bytes; the limit is 512,000.", "analysis_id": "…" } }
```

| Condition | HTTP | Code |
|---|---|---|
| Malformed JSON, schema error or invalid `rules` | 400 | `INVALID_REQUEST`. A custom handler is needed, because FastAPI returns 422 by default. |
| Empty or whitespace-only source | 400 | `INPUT_EMPTY` |
| Source over 512,000 bytes, or body over 3,200,000 bytes | 413 | `INPUT_TOO_LARGE` |
| `language` is not `"c"` | 422 | `UNSUPPORTED_LANGUAGE` |
| Too many requests from one IP | 429 | `RATE_LIMITED` |
| Analysis exceeded the timeout | 503 | `ANALYSIS_TIMEOUT` |
| No analysis slot free within the queue wait | 503 | `SERVICE_UNAVAILABLE` |
| Unexpected failure | 500 | `INTERNAL_ERROR` |

The checks run in this order, so the cheapest rejections come first:
1. rate limit
2. body size
3. JSON and schema
4. `language`
5. source size
6. empty source
7. queue

`INPUT_UNSUPPORTED_TYPE` (uploading a file that isn't `.c`) is handled only in the frontend, because uploads are read in the browser into `source`.

### 8.4 Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ANALYSIS_TIMEOUT_SECONDS` | 5 | Per-analysis timeout |
| `MAX_CONCURRENT_ANALYSES` | 2 | Worker processes and semaphore slots |
| `QUEUE_WAIT_SECONDS` | 3 | Maximum wait for a free slot |
| `RATE_LIMIT_PER_MINUTE` | 30 | Per-IP analyses per minute (0 disables) |
| `TRUST_PROXY_HEADERS` | false | Use `X-Forwarded-For` for the client IP (set to true on Render) |
| `CORS_ORIGINS` | empty | Comma-separated allowed origins |
| `VITE_API_URL` (frontend) | `http://localhost:8000` | API base URL |

## 9. Frontend (Vite + React + TypeScript)

- **Editor.** Monaco, bundled locally (no CDN), so offline lab demos work.
- **Toolbar.**
  - Analyze and Clear.
  - Upload `.c`: any other file type is rejected with `INPUT_UNSUPPORTED_TYPE`, and the 512,000-byte size check runs before sending.
  - An Examples menu. One example is the SRS demo: an unused variable plus `if (10 > 5)`.
- **Stage status bar.** The four stages, each shown as passed, failed or skipped with an icon and a text label.
- **Diagnostics.**
  - Separate tabs for errors, warnings and suggestions, with syntax-stage errors shown separately from later warnings.
  - Severity is shown with an icon and a text label, never by color alone.
  - Clicking a diagnostic jumps to and highlights its line.
  - Every diagnostic shows its explanation and its fix hint, if there is one.
- **Statistics panel.**
- **Teaching views (core features).**
  - Token table.
  - AST as a collapsible tree.
  - Symbol table grouped by scope.
  - When `truncated` is set, the view shows a notice.
- **Safe rendering.** All diagnostic and source-derived text is rendered as plain text, and `dangerouslySetInnerHTML` is never used.
- **Accessibility (WCAG 2.1 AA).**
  - Full keyboard navigation and a visible focus indicator.
  - Labelled controls.
  - An `aria-live` status region that announces results.
  - A visible hint for Monaco's Tab-trapping toggle (Ctrl+M, or Ctrl+Shift+M on macOS).
- **Wake-up message.** On load, the frontend pings `/health`. If that takes more than 2 s, it shows "Waking up the server, this can take about a minute."
- **Error envelopes** are shown as a message along with the `analysis_id`.

## 10. Test plan

### 10.1 SRS acceptance tests, as amended

| ID | Scenario | Expected |
|---|---|---|
| TC-01 | Valid C declaration | Lexical and syntax pass |
| TC-02 | Unused variable | SEM-UNUSED warning |
| TC-03 | Duplicate variable | SEM-DUP error |
| TC-04 | Undeclared variable | SEM-UNDECL error |
| TC-05 | `10 / 0` | SEM-DIV0 error only (no OPT-CONSTEXPR) |
| TC-06 | Statement after `return` | SEM-UNREACH warning |
| TC-07 | `if (10 > 5)` | SEM-CONSTCOND warning only |
| TC-08 | `10 + 20` | OPT-CONSTEXPR suggestion "30" |
| TC-09 | Source of exactly 512,000 bytes | 200 |
| TC-10 | Source of 512,001 bytes | 413 `INPUT_TOO_LARGE` |
| TC-11 | Malformed API JSON | 400 `INVALID_REQUEST` |
| TC-12 | 20 concurrent small analyses | All return 200; P95 ≤ 2 s, P99 ≤ 5 s on a warm server |

### 10.2 Added tests

| ID | Scenario | Expected |
|---|---|---|
| TC-13 | Invalid character `@` | LEX-INVALID-CHAR with line and column; later stages skipped |
| TC-14 | Unterminated string, character literal and block comment | LEX-UNTERMINATED-STRING, -CHAR and -COMMENT respectively |
| TC-15 | Missing `;` | SYN-MISSING-SEMICOLON on the line where `;` belongs |
| TC-16 | Unmatched `{` | SYN-UNMATCHED-BRACE at the opening brace |
| TC-17 | Three independent syntax errors | Three SYN-* diagnostics (recovery) |
| TC-18 | Nested-scope resolution | Inner use resolves to the nearest declaration; no false SEM-UNDECL |
| TC-19 | Shadowing | One SEM-SHADOW |
| TC-20 | `x / y` | No SEM-DIV0 |
| TC-21 | `const int z = 0; x / z` | SEM-DIV0 |
| TC-22 | `x % 0` | SEM-DIV0 |
| TC-23 | `while (1)` | No SEM-CONSTCOND |
| TC-24 | `if (0) { … }` | Exactly one diagnostic (SEM-CONSTCOND) |
| TC-25 | `#include <stdio.h>` + `printf("hi");` | No diagnostics |
| TC-26 | `#define N 10` then use of `N` | No SEM-UNDECL |
| TC-27 | `int a[5];` | UNSUPPORTED_CONSTRUCT "Arrays are not supported in CodeGuard V1." |
| TC-28 | 65 nested blocks | NESTING_TOO_DEEP, no RecursionError |
| TC-29 | Empty or whitespace source | 400 `INPUT_EMPTY` |
| TC-30 | `language: "python"` | 422 `UNSUPPORTED_LANGUAGE` |
| TC-31 | Forced slow analysis via a test hook | 503 `ANALYSIS_TIMEOUT` |
| TC-32 | Response shape | `tokens`, `ast` and `symbols` present and valid |
| TC-33 | Forced internal failure | 500 envelope without a stack trace |
| TC-34 | `<script>` payload in a string literal | Returned as inert text; the frontend renders it as text |
| TC-35 | `int x; scanf("%d", &x);` with no other use of `x` | No UNSUPPORTED_CONSTRUCT; `x` has 1 write and 0 reads; SEM-UNUSED fires on `x` |
| TC-36 | Prototype then definition | No SEM-DUP |
| TC-37 | `break;` outside a loop | SEM-BREAK-CONTEXT error; syntax stage passed |
| TC-38 | Worst case run in the real worker process: 64 nested blocks around 64 nested parentheses, a 256-link `else if` chain and a 256-deep unary chain | Completes with no `RecursionError`; no `NESTING_TOO_DEEP` |
| TC-39 | Input with more than 10,000 tokens | `tokens` view truncated with `truncated.tokens = true`; `statistics.tokens` equals the full count |

Every rule also has at least one positive and one negative unit test. The frontend tests (Vitest + Testing Library) cover:
- the editor, Analyze and Clear
- upload rejection
- the three diagnostic tabs
- the AST and symbol views
- the keyboard path through the main controls

### 10.3 Load test (outside CI)

A script sends 20 concurrent small requests, plus inputs of 1 KB, 10 KB, 100 KB and 500 KB, and reports P95 and P99 latency. Targets: P95 ≤ 2 s and P99 ≤ 5 s on a warm server. Results on the free host are reported as measured, and large inputs may miss the target there.

### 10.4 Traceability

| Requirement group | Tests |
|---|---|
| FR-INPUT | TC-09, TC-10, TC-29, frontend upload tests |
| FR-LEX | TC-01, TC-13, TC-14, lexer unit tests |
| FR-SYN | TC-01, TC-15–17, TC-27, TC-28, TC-35, TC-36, TC-38, parser unit tests |
| FR-SEM | TC-02–07, TC-18–26, TC-35, TC-37, rule unit tests |
| FR-OPT | TC-05, TC-08, optimizer unit tests |
| FR-REPORT | TC-01–08, TC-32, TC-39 |
| API | TC-09–12, TC-29–33, TC-38 |
| NFR-PERF | TC-12, load test |
| Security | TC-10, TC-33, TC-34, no-execution check |
| UI | Vitest suite, manual accessibility check |

## 11. Stated limitations (V1)

- **No preprocessing.** `#include` files aren't read. `#define` values are neither expanded nor folded, so `while (TRUE)` is not reported. Function-like macros are ignored. Every branch of `#if`/`#ifdef` is analyzed.
- **Library names** come from a fixed list (§2.3). A library function that's missing from the list is reported as undeclared, and library signatures aren't checked.
- **No type checking.** CodeGuard doesn't check assigning a string to an `int`, `void` variables, argument counts, return types, or calling a variable as a function.
- **No flow analysis.** Unreachable-code detection only covers code after a jump in the same block. Uninitialised use isn't detected.
- **Folding** assumes 32-bit `int` and IEEE `double`.
- **Single file only.** Identifiers are ASCII, and columns count code points, so a column can differ by one after characters outside the Basic Multilingual Plane, such as emoji.
- **Unsupported constructs** (§2.4) stop semantic analysis for that file.

## 12. Requirements-change log

| # | Decision | SRS IDs affected | Change |
|---|---|---|---|
| 1 | Define the C subset with an EBNF grammar | §1 "Target Language", §2.6, FR-LEX-01, FR-SYN-01…06 | Subset defined by §2–3 of this addendum |
| 2 | Functions, prototypes, calls, `return` | FR-SYN | **New FR-SYN-11 (Must)** |
| 3 | `while`, `for`, `break`, `continue` | FR-SYN | **New FR-SYN-12 (Must)** |
| 4 | Unary, logical and compound-assignment operators; `&name` in call arguments | FR-SYN-03, FR-SYN-04 | Extended (§3.3) |
| 5 | Build an AST | FR-SYN-10 | **Should → Must** |
| 6 | Panic-mode recovery, up to 20 errors | §3.7, FR-SYN-07 | **New FR-SYN-13 (Must)** |
| 7 | `UNSUPPORTED_CONSTRUCT` for §2.4 | §1.2 out of scope | **New FR-SYN-14 (Must)** |
| 8 | Nesting limit, `NESTING_TOO_DEEP` | §2.6 | **New FR-SYN-15 (Must)** |
| 9 | Comments, escapes, hex and octal literals | FR-LEX-03 | Extended; **new FR-LEX-08 (Must)**: comments, unterminated-comment error |
| 10 | Preprocessor lines skipped; object-like `#define` registered | — | **New FR-LEX-09 (Must)** |
| 11 | Token table in the UI | FR-LEX-07, UI-07 | **Should → Must**; the two are one requirement |
| 12 | Built-in library-name list | — | **New FR-SEM-11 (Must)** |
| 13 | "Unused" means "never read" | FR-SEM-04 | Defined (§5.3) |
| 14 | Division by zero: literals, `const` folding, `%` | FR-SEM-05, §3.10 | Defined (§5.3) |
| 15 | Unreachable code: after `return`/`break`/`continue` only | FR-SEM-06 | Defined; `if (0)` excluded |
| 16 | Merge constant-condition rules into SEM-CONSTCOND, owned by semantics | FR-SEM-07, FR-OPT-02, FR-OPT-03 | **Merged**; FR-OPT-02 and FR-OPT-03 withdrawn |
| 17 | `while (1)` and `for (;;)` exempt | FR-SEM-07 | Added |
| 18 | Nested scopes | FR-SEM-09 | **Should → Must** |
| 19 | Shadowing | FR-SEM-10 | **Could → Should**; on by default, can be turned off |
| 20 | One diagnostic per construct | §3.9 | **New FR-SEM-12 (Must)** |
| 21 | Constant-expression suggestion with replacement value | FR-OPT-01, FR-OPT-05 | FR-OPT-05 **Should → Must** |
| 22 | Explanation required on every diagnostic; end positions; `fix_hint` | §3.9, FR-OPT-04 | Explanation **optional → required** for all rules |
| 23 | Stage status passed/failed/skipped for four stages | FR-REPORT-01, UI-03 | Extended |
| 24 | Statistics extended (functions, tokens, lines, duration) | FR-REPORT-04 | Extended |
| 25 | Response includes `tokens`, `ast`, `symbols` | FR-REPORT-05, §3.15 | Extended |
| 26 | AST tree view | — | **New UI-09 (Must)** |
| 27 | Symbol table view grouped by scope | — | **New UI-10 (Must)** |
| 28 | Click a diagnostic to jump to its line | UI-05 | **Should → Must** |
| 29 | Examples menu including the SRS demo | FR-INPUT-06 | **Should → Must** |
| 30 | Wake-up message | — | **New UI-11 (Must)** |
| 31 | Tab-trap hint for Monaco | UI-08 | Clarified |
| 32 | Monaco bundled locally | §2.3, §2.5 | Clarified: no CDN |
| 33 | Size limit is 512,000 UTF-8 bytes of `source` | FR-INPUT-04, NFR-PERF-03, §2.6 | "500 KB" defined |
| 34 | Health endpoint | §3.15 | **New** `GET /api/v1/health` |
| 35 | `analysis_id` is a per-request trace UUID, never stored | §3.15, §6 | Clarified |
| 36 | Timeout returns 503, enforced with a worker process | §3.16 | **408 → 503** `ANALYSIS_TIMEOUT` |
| 37 | Malformed JSON returns 400 via a custom handler | §3.16, TC-11 | Kept at 400 (FastAPI's default is 422) |
| 38 | Added error codes `INPUT_EMPTY` (400), `SERVICE_UNAVAILABLE` (503), `RATE_LIMITED` (429) | §3.16, §7.1 | Added to the API table |
| 39 | `INPUT_UNSUPPORTED_TYPE` is frontend-only | §7.1 | Clarified |
| 40 | Concurrency: 2 slots plus a 3 s queue | NFR-PERF-04, TC-12 | Defined; TC-12 means all 20 return 200 |
| 41 | Latency targets apply to a warm server | NFR-PERF-01, NFR-PERF-02 | Clarified |
| 42 | Availability, RPO and RTO | §5.3 | **Withdrawn (Won't for V1)**; "malformed request must not crash" kept |
| 43 | Server is the Render free tier (512 MB) | §2.5 | Replaces the 2-core/4 GB assumption |
| 44 | V1 is stateless; no source stored; no accounts | §6.1–6.4 | **Replaced**; User/SourceCode entities and retention periods withdrawn |
| 45 | Log only source length and hash | §5.2 | Tightened |
| 46 | Per-IP rate limiting | §5.2 | Defined (§7) |
| 47 | Pointers, arrays, struct/union/enum, typedef, switch, do/while, goto, ternary, casts, sizeof unsupported | §1.2 | Added to out of scope |
| 48 | `&name` allowed only as a call argument (for `scanf`) | — | Decided in planning (2026-10-16) |
| 49 | Prototypes supported; extra type words, storage classes, bitwise and comma operators unsupported | — | Decided in planning (2026-10-16) |
| 50 | SEM-CONSTCOND moves to Member 2; serialization moves to Member 3 | §8.1 | Team allocation updated (see `CONTRIBUTING.md`) |
| 51 | Added tests TC-13 to TC-39; traceability corrected | §9.1, §9.2 | Replaced by §10 |
| 52 | Recursion safety: precedence climbing; iterative chains and AST passes; worst-case test; no `setrecursionlimit` | FR-SYN-15, §2.6 | **Amended 2026-10-16** (§4.1, §7, TC-38) |
| 53 | Nesting limits split: statements ≤ 64, parentheses ≤ 64 (counted separately), chains ≤ 256 | FR-SYN-15 | **Amended 2026-10-16** |
| 54 | Token/AST caps apply to the teaching views only; statistics cover the full input | FR-REPORT-04, FR-REPORT-05 | **Amended 2026-10-16** (TC-39) |
| 55 | `break`/`continue` outside a loop is the semantic constraint check SEM-BREAK-CONTEXT, not a syntax error | — | **New FR-SEM-13 (Must)**, amended 2026-10-16 (TC-37) |
| 56 | `&x` in a call argument counts as a write, so `int x; scanf("%d", &x);` alone gives SEM-UNUSED | FR-SEM-04 | **Amended 2026-10-16** (TC-35) |
| 57 | Timeout via a pool of long-lived worker processes (`pebble`), killed and replaced on timeout; pool size = concurrency limit | §3.16, NFR-PERF-04 | **Amended 2026-10-16** |
