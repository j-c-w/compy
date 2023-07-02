#include<stdio.h>

int *a;
int main() {
    for (int i = 0; i < 100; i ++) {
        a[i] += 1;
    }
    printf("Hello world\n");
    return 0;
}
