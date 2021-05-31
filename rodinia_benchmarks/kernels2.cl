typedef struct {
  float weight;
  //float *coord;
  long assign;  /* number of point where this one is assigned */
  float cost;  /* cost of that assignment, weight*distance */
} Point_Struct;


//#define Elements
__kernel void memset_kernel(__global char * mem_d, short val, int number_bytes){
	const int thread_id = get_global_id(0);
	mem_d[thread_id] = val;
}