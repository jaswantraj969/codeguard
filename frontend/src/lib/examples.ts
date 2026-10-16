export interface Example {
  id: string
  title: string
  source: string
}

/** The SRS demonstration program (SRS §3.13): an unused variable plus if (10 > 5). */
export const SRS_DEMO: Example = {
  id: 'srs-demo',
  title: 'SRS demo: unused variable and constant condition',
  source: `#include <stdio.h>

int main(void) {
    int x = 10;
    int unused = 50;

    if (10 > 5) {
        printf("x is %d\\n", x);
    }
    return 0;
}
`,
}

export const EXAMPLES: Example[] = [
  SRS_DEMO,
  {
    id: 'arithmetic',
    title: 'Division by zero and constant expressions',
    source: `#include <stdio.h>

#define LIMIT 100

int main(void) {
    const int zero = 0;
    int seconds = 24 * 60 * 60;
    int ratio = seconds / zero;
    int half = 7 / 2;

    printf("%d %d %d\\n", ratio, half, LIMIT);
    return 0;
}
`,
  },
  {
    id: 'scopes',
    title: 'Scopes, shadowing and undeclared names',
    source: `int count = 0;

int add(int a, int b) {
    int count = a + b;
    return count;
}

int main(void) {
    for (int i = 0; i < 3; i++) {
        count = add(count, i);
    }
    return total;
}
`,
  },
  {
    id: 'control-flow',
    title: 'Loops and unreachable code',
    source: `#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);

    while (1) {
        if (n <= 0) {
            break;
        }
        n--;
    }

    while (0) {
        n++;
    }

    return n;
    printf("done\\n");
}
`,
  },
  {
    id: 'syntax-errors',
    title: 'Syntax errors',
    source: `int main(void) {
    int x = 5
    int y = (x + 2;
    if (x > y) {
        x = y;
    return 0;
}
`,
  },
  {
    id: 'unsupported',
    title: 'Constructs outside the V1 subset',
    source: `int main(void) {
    int scores[3];
    int *p;
    return 0;
}
`,
  },
]
